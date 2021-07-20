import random
import logging
from logging import Logger
from abc import ABC, abstractmethod

from typing import Optional, Any


class DocCacheBuilder(ABC):
    """
    __DocCacheBuilder__
    General Abstract Base Class for building caching documents
    """

    def __init__(self, default: Any = {}, logger: Optional[Logger] = None) -> None:
        try:
            super().__init__()
            self.default = default
            self.lifeTimeMinutes = int(20 + random.random() * 10)

            logging.basicConfig(level=logging.INFO)
            self.logger = logger or logging.getLogger(self.__class__.__name__)

        except Exception as error:
            raise Exception(f"Error initializing DocCacheBuilder\n{str(error)}")

    @abstractmethod
    def get(self) -> Any:
        """
        The function to get the caching data
        """
        pass
