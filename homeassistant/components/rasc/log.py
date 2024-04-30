"""Support for rasc."""
from __future__ import annotations

import datetime
import logging
import os
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Trail:
    """A class for recording trail."""

    def __init__(self) -> None:
        """Initialize the trail."""
        self.num = 0

    def increment(self) -> None:
        """Increase the trail."""
        self.num += 1


TRAIL = Trail()


def set_log_dir() -> str:
    """Set log path."""
    fp = "testrun-" + datetime.datetime.now().strftime("%Y-%m-%d")

    if os.path.isdir(fp):
        shutil.rmtree(fp)
    os.mkdir(fp)

    return fp


LOG_PATH = set_log_dir()


def set_logger() -> logging.Logger:
    """Set logger."""
    logger = logging.getLogger("rascal_logger")
    logger.setLevel(logging.DEBUG)
    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    filename = os.path.join(LOG_PATH, "rascal.log")
    log_handler = logging.FileHandler(filename, mode="w")
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    return logger
