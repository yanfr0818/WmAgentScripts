from collections import defaultdict, Mapping
from Utilities.IteratorTools import mapValues, filterKeys

from typing import Optional, List, Tuple


def countLumisPerFile(filesPerLumis: dict) -> dict:
    """
    The function to count the number of lumis per file
    :param filesPerLumis: dict of files by lumis
    :return: dict of lumis by files
    """
    try:
        lumisPerFile = defaultdict(int)
        for _, files in filesPerLumis.items():
            for file in files:
                lumisPerFile[file] += 1
        return lumisPerFile

    except Exception as error:
        print("Failed to count lumis per file")
        print(str(error))


def filterRecoveryFilesAndLocations(recoveryDocs: List[dict], suffixTaskFilter: Optional[str] = None) -> dict:
    """
    The function to filter the files and locations for the given recovery docs
    :param recoveryDocs: recovery docs
    :param suffixTaskFilter: filter tasks ending with given suffix
    :return: a dict of files and locations
    """
    filesAndLocations = defaultdict(set)
    for doc in recoveryDocs:
        task = doc.get("fileset_name", "")
        if suffixTaskFilter and not task.endswith(suffixTaskFilter):
            continue

        for filename, data in doc["files"].items():
            filesAndLocations[filename].update(data.get("locations", []))

    filesAndLocations = mapValues(list, filesAndLocations)

    print(f"{len(filesAndLocations)} files in recovery")
    return filesAndLocations


def filterFilesAndLocationsInDBS(filesAndLocations: dict) -> Tuple[dict, dict]:
    """
    The function to filter the files in DBS and the files not in DBS
    :param filesAndLocations: dict of files and locations
    :return: two dicts of files and locations
    """
    filesInDBS, filesNotInDBS = set(), set()
    for filename in filesAndLocations:
        if any(filename.startswith(location) for location in ["/store/unmerged/", "MCFakeFile-"]):
            filesNotInDBS.add(filename)
        else:
            filesInDBS.add(filename)

    inDBS = mapValues(list, filterKeys(filesInDBS, filesAndLocations))
    notInDBS = mapValues(list, filterKeys(filesNotInDBS, filesAndLocations))
    return inDBS, notInDBS


def filterLumisAndFilesByRuns(filesByLumis: dict, lumisByRun: dict, runs: list) -> Tuple[dict, dict]:
    """
    The function to get the lumi sections and files filtered by given runs
    :param filesByLumis: a dict of format {run: [lumis]}
    :param lumisByRun: a dict of format {(run:lumis): [files]}
    :param runs: run numbers
    :return: a dict of format {run: [lumis]} and a dict of format {(run:lumis): [files]}
    """
    return filterKeys(runs, lumisByRun, filesByLumis)


def filterLumisAndFilesByLumis(filesByLumis: dict, lumisByRun: dict, lumis: dict) -> Tuple[dict, dict]:
    """
    The function to get the lumi sections and files filtered by given lumi sections
    :param filesByLumis: a dict of format {run: [lumis]}
    :param lumisByRun: a dict of format {(run:lumis): [files]}
    :param lumis: a dict of format {run: [lumis]}
    :return: a dict of format {run: [lumis]} and a dict of format {(run:lumis): [files]}
    """
    runs = map(int, lumis.keys())
    lumis = set((k, vi) for k, v in lumis.items() for vi in v)
    lumisByRun = filterKeys(runs, lumisByRun)
    filesByLumis = filterKeys(lumis, filesByLumis)
    return lumisByRun, filesByLumis


def filterSplittingsTaskTypes(splittings: List[dict]) -> List[dict]:
    """
    The function to filter tasks types in splittings schema
    :param splittings: workflow name
    :return: a list of dicts where task types are production, processing or skim
    """
    tasksToKeep = ["Production", "Processing", "Skim"]
    return [splt for splt in splittings if splt["taskType"] in tasksToKeep]


def filterSplittingsParam(splittings: List[dict]) -> List[dict]:
    """
    The function to drop params from splittings schema
    :param splittings: workflow name
    :return: a list of dicts
    """
    paramsToDrop = [
        "algorithm",
        "trustPUSitelists",
        "trustSitelists",
        "deterministicPileup",
        "type",
        "include_parents",
        "lheInputFiles",
        "runWhitelist",
        "runBlacklist",
        "collectionName",
        "group",
        "couchDB",
        "couchURL",
        "owner",
        "initial_lfn_counter",
        "filesetName",
        "runs",
        "lumis",
    ]
    lumiBasedParamsToDrop = ["events_per_job", "job_time_limit"]

    cleanSplittings = []
    for splt in splittings:
        for param in paramsToDrop:
            splt["splitParams"].pop(param, None)

        if splt["splitAlgo"] is "LumiBased":
            for param in lumiBasedParamsToDrop:
                splt["splitParams"].pop(param, None)
        cleanSplittings.append(splt)
    return cleanSplittings


def deepUpdate(toUpdate: dict, data: dict) -> dict:
    """
    The function to deep update a given dictionary
    :param toUpdate: dict to update
    :param data: data to updatade dict
    :return: updated dict
    """
    for k, v in data.items():
        if isinstance(v, dict) or isinstance(v, Mapping):
            defaultValue = v.copy()
            defaultValue.clear()
            v = deepUpdate(toUpdate.get(k, defaultValue), v)

        toUpdate[k] = v
    return toUpdate
