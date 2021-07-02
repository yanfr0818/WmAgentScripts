"""
File       : DBSReader.py
Author     : Hasan Ozturk <haozturk AT cern dot com>
Description: General API for reading data from DBS
"""

import os
import logging
from logging import Logger
from collections import defaultdict
from dbs.apis.dbsClient import DbsApi

from Utils.ConfigurationHandler import ConfigurationHandler
from Utils.Decorators import runWithMultiThreading
from Services.Mongo.CacheInfo import CacheInfo

from typing import Callable, Optional, List, Tuple


class DBSReader(object):
    """
    _DBSReader_
    General API for reading data from DBS
    """

    def __init__(
        self, url: Optional[str] = None, logger: Optional[Logger] = None, **contact
    ):
        try:
            if url:
                self.dbsUrl = url.replace("cmsweb.cern.ch", "cmsweb-prod.cern.ch")
            else:
                configurationHandler = ConfigurationHandler()
                self.dbsUrl = os.getenv(
                    "DBS_READER_URL", configurationHandler.get("dbs_url")
                )
            self.dbs = DbsApi(self.dbsUrl, **contact)
            self.cache = CacheInfo()
            logging.basicConfig(level=logging.INFO)
            self.logger = logger or logging.getLogger(self.__class__.__name__)

        except Exception as e:
            msg = "Error in DBSReader with DbsApi\n"
            msg += f"{e}\n"
            raise Exception(msg)

    def check(self) -> bool:
        """
        The function to check dbs is responding
        """
        try:
            if "testbed" in self.dbsUrl:
                checkDataset = "/QDTojWinc_NC_M-1200_TuneZ2star_8TeV-madgraph/Summer12pLHE-DMWM_Validation_DONOTDELETE_Alan_TEST-v1/GEN"
            else:
                checkDataset = "/TTJets_mtop1695_TuneCUETP8M1_13TeV-amcatnloFXFX-pythia8/RunIIWinter15GS-MCRUN2_71_V1-v1/GEN-SIM"
            response = self.dbs.listBlockSummaries(dataset=checkDataset, detail=True)
            if not response:
                raise Exception("DBS corrupted")
            return True

        except Exception as error:
            self.logger.error("Failed to get any response from DBS")
            self.logger.error(str(error))
            return False

    @runWithMultiThreading
    def _getFileLumiArray(self, filenames: List[str], run: int) -> List[dict]:
        # TODO: (for when the environment is deployed) test if it is working properly with mt
        """
        The function to get the lumi section arrays for a given set of file names in given run
        :param filename: logical file names
        :param run: run number
        :return: a list of lumi section arrays

        This function runs by default with multithreading and a list of
        dicts, e. g. [{'filename': filename, 'run': run}], must be given as input.
        """
        try:
            return (
                self.dbs.listFileLumiArray(logical_file_name=filenames, run_num=run)
                if run != 1
                else self.dbs.listFileLumiArray(logical_file_name=filenames)
            )

        except Exception as error:
            self.logger.error("Failed to get lumi array files")
            self.logger.error(str(error))

    @runWithMultiThreading
    def _getBlockFileLumis(self, block: str, validFileOnly: bool = True) -> List[dict]:
        # TODO: (for when the environment is deployed) test if it is working properly with mt
        """
        The function to get lumi section files from a given block
        :param block: block name
        :param validFileOnly: if True, keeps only valid files, keep all o/w
        :return: lumi sections files

        This function runs by default with multithreading and a list of
        dicts, e. g. [{'block': block}] must be given as input.
        """
        try:
            return self.dbs.listFileLumis(
                block_name=block, validFileOnly=int(validFileOnly)
            )

        except Exception as error:
            self.logger.error("Failed to get files from DBS for block %s", block)
            self.logger.error(str(error))

    def getDBSStatus(self, dataset: str) -> str:
        """
        The function to get the DBS status of a given dataset
        :param dataset: dataset name
        :return: DBS status
        """
        try:
            response = self.dbs.listDatasets(
                dataset=dataset, dataset_access_type="*", detail=True
            )
            dbsStatus = response[0]["dataset_access_type"]
            self.logger.info(f"{dataset} is {dbsStatus}")
            return dbsStatus

        except Exception as error:
            self.logger.error(
                "Exception while getting the status of following dataset on DBS: %s",
                dataset,
            )
            self.logger.error(str(error))

    def getFilesWithLumiInRun(self, dataset: str, run: int) -> List[dict]:
        """
        The function to get the files with lumi sections for a given dataset in a given run
        :param dataset: dataset name
        :param run: run number
        :return: a list of files with lumi sections
        """
        try:
            result = (
                self.dbs.listFiles(
                    dataset=dataset, detail=True, run_num=run, validFileOnly=1
                )
                if run != 1
                else self.dbs.listFiles(dataset=dataset, detail=True, validFileOnly=1)
            )
            filenames = [file["logical_file_name"] for file in result]

            querySize = 100
            queryFilesList = [
                {"filenames": filenames[i : i + querySize], "run": run}
                for i in range(0, len(filenames), querySize)
            ]
            return self._getFileLumiArray(queryFilesList)

        except Exception as error:
            self.logger.error(
                "Failed to get files for dataset %s and run %s", dataset, run
            )
            self.logger.error(str(error))

    def getBlockName(self, filename: str) -> str:
        """
        The function to get the block name for a given file
        :param filename: logical file name
        :return: block name
        """
        try:
            result = self.dbs.listFileArray(logical_file_name=filename, detail=True)
            return result[0]["block_name"]

        except Exception as error:
            self.logger.error("Failed to get block name from DBS for file %s", filename)
            self.logger.error(str(error))

    def getDatasetFiles(
        self, dataset: str, validFileOnly: bool = False, details: bool = False
    ) -> List[dict]:
        """
        The function to get the files for a given dataset
        :param dataset: dataset name
        :param validFileOnly: if True, keep only valid files, keep all o/w
        :param details: if True, returns details for each file, o/w only keep file names and validity
        :return: a list of files
        """
        try:
            cacheKey = f"dbs_listFile_{dataset}"
            cached = self.cache.get(cacheKey)
            if cached:
                self.logger.info("listFile of %s taken from cache", dataset)
                files = cached
            else:
                files = self.dbs.listFiles(dataset=dataset, detail=True)
                self.logger.info("Caching listFile of %s", dataset)
                self.cache.store(cacheKey, files)

            if validFileOnly:
                files = [file for file in files if file["is_file_valid"]]

            if not details:
                keysToKeep = ["logical_file_name", "is_file_valid"]
                files = list(filterKeys(keysToKeep, *files))

            return files

        except Exception as error:
            self.logger.error(
                "Failed to get file array from DBS for dataset %s", dataset
            )
            self.logger.error(str(error))

    def getDatasetBlockNames(self, dataset: str) -> List[str]:
        """
        The function to get the block names of a given dataset
        :param dataset: dataset name
        :return: a list of block names
        """
        try:
            result = self.dbs.listBlocks(dataset=dataset)
            blocks = set()
            blocks.update(block["block_name"] for block in result)
            return list(blocks)

        except Exception as error:
            self.logger.error(
                "Failed to get block names from DBS for dataset %s", dataset
            )
            self.logger.error(str(error))

    def getDatasetBlockNamesByRuns(self, dataset: str, runs: list) -> List[str]:
        """
        The function to get the block names of a given dataset in the given runs
        :param dataset: dataset name
        :param runs: run numbers
        :return: a list of block names
        """
        try:
            blocks = set()
            for run in map(int, runs):
                result = (
                    self.dbs.listBlocks(dataset=dataset, run_num=run)
                    if run != 1
                    else self.dbs.listBlocks(dataset=dataset)
                )
                blocks.update(block["block_name"] for block in result)
            return list(blocks)

        except Exception as error:
            self.logger.error(
                "Failed to get block names from DBS for dataset %s", dataset
            )
            self.logger.error(str(error))

    def getDatasetBlockNamesByLumis(self, dataset: str, lumisByRun: dict) -> List[str]:
        """
        The function to get the block names of a given dataset in the given lumi sections
        :param dataset: dataset name
        :param lumisByRun: a dict of format {run: [lumis]}
        :return: a list of block names
        """
        try:
            blocks = set()
            for run, lumiList in lumisByRun.items():
                if int(run) != 1:
                    result = self.dbs.listFileArray(
                        dataset=dataset,
                        lumi_list=lumiList,
                        run_num=int(run),
                        detail=True,
                    )
                else:
                    # NOTE: dbs api does not support run_num=1 w/o defining a logical_file_name
                    # To avoid the exception, in this case make the call with filenames instead of lumis
                    files = self.getDatasetFiles(dataset)
                    filenames = [file["logical_file_name"] for file in files]
                    result = self.dbs.listFileArray(
                        dataset=dataset,
                        logical_file_names=filenames,
                        run_num=int(run),
                        detail=True,
                    )
                blocks.update(block["block_name"] for block in result)
            return list(blocks)

        except Exception as error:
            self.logger.error(
                "Failed to get block names from DBS for dataset %s", dataset
            )
            self.logger.error(str(error))

    def getDatasetSize(self, dataset: str) -> float:
        """
        The function to get the size (in terms of GB) of a given dataset
        :param dataset: dataset name
        :return: dataset size
        """
        try:
            blocks = self.dbs.listBlockSummaries(dataset=dataset, detail=True)
            return sum([block["file_size"] for block in blocks]) / (1024.0 ** 3)

        except Exception as error:
            self.logger.error("Failed to get size of dataset %s from DBS", dataset)
            self.logger.error(str(error))

    def getDatasetEventsAndLumis(self, dataset: str) -> Tuple[int, int]:
        """
        The function to get the total number of events and lumi sections for a given dataset
        :param dataset: dataset name
        :return: total number of events and of lumi sections
        """
        try:
            files = self.dbs.listFileSummaries(dataset=dataset, validFileOnly=1)
            events = sum([file["num_event"] for file in files if file is not None])
            lumis = sum([file["num_lumi"] for file in files if file is not None])
            return events, lumis

        except Exception as error:
            self.logger.error("Failed to get events and lumis from DBS")
            self.logger.error(str(error))

    def getBlocksEventsAndLumis(self, blocks: List[str]) -> Tuple[int, int]:
        """
        The function to get the total number of events and lumi sections for given blocks
        :param blocks: blocks names
        :return: total number of events and of lumi sections
        """
        try:
            files = []
            for block in blocks:
                files.extend(
                    self.dbs.listFileSummaries(block_name=block, validFileOnly=1)
                )
            events = sum([file["num_event"] for file in files if file is not None])
            lumis = sum([file["num_lumi"] for file in files if file is not None])
            return events, lumis

        except Exception as error:
            self.logger.error("Failed to get events and lumis from DBS")
            self.logger.error(str(error))

    def getDatasetRuns(self, dataset: str) -> List[int]:
        """
        The function to get the runs for a given dataset
        :param dataset: dataset name
        :return: a list of run numbers
        """
        try:
            result = self.dbs.listRuns(dataset=dataset)
            runs = []
            for run in result:
                if isinstance(run["run_num"], list):
                    runs.extend(run["run_num"])
                else:
                    runs.append(run["run_num"])
            return runs

        except Exception as error:
            self.logger.error("Failed to get runs from DBS for dataset %s", dataset)
            self.logger.error(str(error))

    def getDatasetParent(self, dataset: str) -> List[str]:
        """
        The function to get the parent dataset of a given dataset
        :param dataset: dataset name
        :return: a list of parent names
        """
        try:
            result = self.dbs.listDatasetParents(dataset=dataset)
            return [item.get("parent_dataset") for item in result]

        except Exception as error:
            self.logger.error("Failed to get parents from DBS for dataset %s", dataset)
            self.logger.error(str(error))

    def getDatasetNames(self, dataset: str) -> List[dict]:
        """
        The function to get the datasets matching a given dataset name
        :param dataset: dataset name
        :return: a list of dicts with dataset names
        """
        try:
            _, datasetName, processedName, tierName = dataset.split("/")
            result = self.dbs.listDatasets(
                primary_ds_name=datasetName,
                processed_ds_name=processedName,
                data_tier_name=tierName,
                dataset_access_type="*",
            )
            return result

        except Exception as error:
            self.logger.error("Failed to get info from DBS for dataset %s", dataset)
            self.logger.error(str(error))

    def getLFNBase(self, dataset: str) -> str:
        """
        The function to get the base of logical file names for a given dataset
        :param dataset: dataset name
        :return: base of logical file names
        """
        try:
            result = self.dbs.listFiles(dataset=dataset)
            filename = result[0]["logical_file_name"]
            return "/".join(filename.split("/")[:3])

        except Exception as error:
            self.logger.error("Failed to get LFN base from DBS for dataset %s", dataset)
            self.logger.error(str(error))

    def getRecoveryBlocks(self, filesAndLocations: dict) -> Tuple[list, dict]:
        """
        The function to get the blocks needed for the recovery of a workflow
        :param filesAndLocations: dict of file names and locations
        :return: all blocks and locations in DBS
        """
        try:
            blocks = set()
            blocksAndLocations = defaultdict(set)
            cachedBlockFiles = defaultdict(str)
            for filename, location in filesAndLocations.items():
                if filename in cachedBlockFiles:
                    blockName = cachedBlockFiles[filename]
                else:
                    blockName = self.getBlockName(filename)
                    if blockName:
                        files = self.getDatasetFileArray(
                            blockName.split("#")[0], details=True
                        )
                        for file in files:
                            cachedBlockFiles[file["logical_file_name"]] = file[
                                "block_name"
                            ]
                            blocks.add(file["block_name"])
                    else:
                        continue
                blocksAndLocations[blockName].update(location)

            blocksAndLocations = mapValues(list, blocksAndLocations)
            return list(blocks), blocksAndLocations

        except Exception as error:
            self.logger.error("Failed to recovery blocks from DBS")
            self.logger.error(str(error))

    def getDatasetLumisAndFiles(
        self, dataset: str, validFileOnly: bool = True, withCache: bool = True
    ) -> Tuple[dict, dict]:
        """
        The function to get the lumis and files of a given dataset
        :param dataset: dataset name
        :param validFileOnly: if True, keep only valid files, o/w keep all
        :param withCache: if True, get cached data, o/w build from blocks
        :return: a dict in the format {run: [lumis]} and a dict in the format {(run:lumis): [files]}
        """
        try:
            cacheKey = f"json_lumis_{dataset}"
            cached = self.cache.get(cacheKey)
            if withCache and cached:
                self.logger.info("json_lumis of %s taken from cache", dataset)
                lumisByRun, filesByLumis = cached["lumis"], cached["files"]
            else:
                blocks = self.dbs.listBlocks(dataset=dataset)
                lumisByRun, filesByLumis = self.getBlocksLumisAndFilesForCaching(
                    blocks, validFileOnly
                )
                self.logger.info("Caching json_lumis of %s", dataset)
                self.cache.store(
                    cacheKey,
                    {"files": filesByLumis, "lumis": lumisByRun},
                    lifeTimeMinutes=600,
                )

            lumisByRun = dict((int(k), v) for k, v in lumisByRun.items())
            filesByLumis = dict(
                (tuple(map(int, k.split(":"))), v) for k, v in filesByLumis.items()
            )
            return lumisByRun, filesByLumis

        except Exception as error:
            self.logger.error(
                "Failed to get lumis and files from DBS for dataset %s", dataset
            )
            self.logger.error(str(error))

    def getBlocksLumisAndFilesForCaching(
        self, blocks: List[dict], validFileOnly: bool = True
    ) -> Tuple[dict, dict]:
        """
        The function to get the lumis and files of given blocks
        :param blocks: blocks
        :param validFileOnly: if True, keep only valid files, keep all o/w
        :return: a dict in the format {'run': [lumis]} and a dict in the format {'run:lumis': [files]}, where the keys are strings
        """
        filesByLumis, lumisByRun = defaultdict(set), defaultdict(set)
        files = self._getBlockFileLumis(
            [
                {"block": block.get("block_name"), "validFileOnly": validFileOnly}
                for block in blocks
            ]
        )
        for file in files:
            runKey = str(file["run_num"])
            lumisByRun[runKey].update(file["lumi_section_num"])
            for lumiKey in file["lumi_section_num"]:
                filesByLumis[f"{runKey}:{lumiKey}"].add(file["logical_file_name"])

        lumisByRun = mapValues(list, lumisByRun)
        filesByLumis = mapValues(list, filesByLumis)
        return lumisByRun, filesByLumis


# TODO: MOVE TO SOMEWHERE ELSE ?
# Maybe some file to put data cleaning functions ?
def filterKeys(lst: list, data: dict, *otherData: dict) -> dict:
    """
    The function to filter dict data by a given list of keys to keep
    :param lst: key values to keep
    :param data/otherData: dicts
    :return: filtered data (keep the input order if more than one dict is given)
    """
    filteredData = []
    for d in [data] + list(otherData):
        filteredData.append(
            dict(
                (k, v)
                for k, v in d.items()
                if k in lst or (isinstance(k, tuple) and k[0] in lst)
            )
        )
    return tuple(filteredData) if len(filteredData) > 1 else filteredData[0]


def mapValues(f: Callable, data: dict) -> dict:
    """
    The function to map the values of a dict by a given function
    :param f: the function to apply to values
    :param data: dict
    :return: dict of format {k: f(v)}
    """
    return dict((k, f(v)) for k, v in data.items())


# TODO: MOVE TO SOMEWHERE ELSE ?
# This is whats done just after getRecoveryDoc(), in getRecoveryBlocks(), in utils.py
def getRecoveryFilesAndLocations(
    recoveryDocs: List[dict], suffixTaskFilter: Optional[str] = None
) -> dict:
    """
    The function to get the files and locations for given recovery docs
    :param recoveryDocs: recovery docs
    :param suffixTaskFilter: filter tasks ending with given suffix
    :return: a dict of files and locations
    """
    filesAndLocations = defaultdict(set)
    for doc in recoveryDocs:
        task = doc.get("fileset_name", "")
        if suffixTaskFilter and not task.endswith(suffixTaskFilter):
            continue

        for filename in doc["files"]:
            filesAndLocations[filename].update(doc["files"][filename]["locations"])
        else:
            filesAndLocations[filename].update([])

    print(f"{len(filesAndLocations)} files in recovery")

    filesAndLocations = mapValues(list, filesAndLocations)
    return filesAndLocations


# This creates half of the original outputs of getRecoveryBlocks(), in utils.py
def splitFilesAndLocationsInDBS(filesAndLocations: dict) -> Tuple[dict, dict]:
    """
    The function to split the files in a subset of files in DBS and of files not in DBS
    :param filesAndLocations: dict of files and locations
    :return: two dicts of files and locations
    """
    filesInDBS, filesNotInDBS = set(), set()
    for filename in filesAndLocations:
        if any(
            filename.startswith(strg) for strg in ["/store/unmerged/", "MCFakeFile-"]
        ):
            filesNotInDBS.add(filename)
        else:
            filesInDBS.add(filename)

    inDBS = filterKeys(filesInDBS, filesAndLocations)
    inDBS = mapValues(list, inDBS)

    notInDBS = filterKeys(filesNotInDBS, filesAndLocations)
    notInDBS = mapValues(list, notInDBS)

    return inDBS, notInDBS


# TODO: MOVE TO SOMEWHERE ELSE ?
# This is whats done in the end of getDatasetLumisAndFiles(), in utils.py when runs != None
def filterLumisAndFilesByRuns(
    filesByLumis: dict, lumisByRun: dict, runs: list
) -> Tuple[dict, dict]:
    """
    The function to get the lumi sections and files filtered by given runs
    :param filesByLumis: a dict of format {run: [lumis]}
    :param lumisByRun: a dict of format {(run:lumis): [files]}
    :param run: run names
    :return: a dict of format {run: [lumis]} and a dict of format {(run:lumis): [files]}
    """
    return filterKeys(runs, lumisByRun, filesByLumis)


# This is whats done in the end of getDatasetLumisAndFiles(), in utils.py when lumis != None
def filterLumisAndFilesByLumis(
    filesByLumis: dict, lumisByRun: dict, lumis: dict
) -> Tuple[dict, dict]:
    """
    The function to get the lumi sections and files filtered by given lumi sections
    :param filesByLumis: a dict of format {run: [lumis]}
    :param lumisByRun: a dict of format {(run:lumis): [files]}
    :param lumis: a dict of format {run: lumis}
    :return: a dict of format {run: [lumis]} and a dict of format {(run:lumis): [files]}
    """
    runs = map(int, lumis.keys())
    lumis = set((k, v) for k, v in lumis.items())
    lumisByRun = filterKeys(runs, lumisByRun)
    filesByLumis = filterKeys(lumis, filesByLumis)
    return lumisByRun, filesByLumis
