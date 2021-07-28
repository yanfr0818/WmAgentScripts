from logging import Logger
from typing import Optional, Tuple

from Components.RequestData.BaseChainRequestDataHandler import BaseChainRequestDataHandler


class StepChainRequestDataHandler(BaseChainRequestDataHandler):
    """
    __StepChainRequestDataHandler__
    General API for handling the request data of step chain request type
    """

    def __init__(self, wfSchema: dict, logger: Optional[Logger] = None) -> None:
        try:
            super().__init__(wfSchema, logger)
            self.includeHEPCloudInSiteWhiteList = True

            self.logMsg = {
                "reduceLargeOutput": "The output size of task is expected to be too large : %d x %.2f kB = %.2f GB > %f GB. Reducing to %d"
            }

        except Exception as error:
            raise Exception(f"Error initializing StepChainRequestDataHandler\n{str(error)}")

    def isGoodToConvertToStepChain(self, _: Optional[list]) -> bool:
        """
        The function to check if a request is good to be converted to step chain.
        :return: False, since the convertion this is already a step chain request
        """
        self.logger.info("Convertion is supported only from TaskChain to StepChain")
        return False

    def getEvents(self) -> int:
        """
        The function to get the number of events in the request
        :return: number of events
        """
        return int(self.get("RequestNumEvents"))

    def getBlowupFactor(self, _: list) -> float:
        """
        The function to get the blow up factor
        :return: 1, since blow up factor does not exist for step chain request
        """
        self.logger.info("Blockup factor only exists for TaskChain")
        return 1.0

    def checkSplittingsSize(self, splittings: dict) -> Tuple[bool, list]:
        """
        The function to check the splittings sizes and if any action is required
        :param splittings: splittings schema
        :return: if to hold and a list of modified splittings
        """
        try:
            modifiedSplittings = []

            nCores = self.getMulticore()
            totalGbSpaceLimit = nCores * self.unifiedConfiguration.get("GB_space_limit")

            sizePerEvent = self.wfSchema.get("SizePerEvent", 0) / (1024.0 ** 2.0)
            for splitting in splittings:
                params = splitting.get("splitParams", {})

                eventsPerJob = params.get("events_per_job", 0)
                size = eventsPerJob * sizePerEvent

                if size > totalGbSpaceLimit:
                    maxTaskEventsPerJob = int(totalGbSpaceLimit / sizePerEvent)
                    splitting["splitParams"]["events_per_job"] = maxTaskEventsPerJob
                    modifiedSplittings.append(splitting)

                    self.logger.info(
                        self.logMsg["reduceLargeOutput"],
                        eventsPerJob,
                        sizePerEvent,
                        size,
                        totalGbSpaceLimit,
                        maxTaskEventsPerJob,
                    )

            return False, modifiedSplittings

        except Exception as error:
            self.logger.error("Failed to check splittings")
            self.logger.error(str(error))

    def writeDatasetPatternName(self, elements: list) -> str:
        """
        The function to write the dataset pattern name from given elements
        :param elements: dataset name elements — name, acquisition era, processing string, version, tier
        :return: dataset name
        """
        try:
            if (elements[3] == "v*" and all(element == "*" for element in elements[1:3])) or (
                elements[3] != "v*" and elements[2] == "*"
            ):
                return None
            return f"/{elements[0]}/{'-'.join(elements[1:4]/{elements[4]})}"

        except Exception as error:
            self.logger.error("Failed to write dataset pattern name for %s", elements)
            self.logger.error(str(error))
