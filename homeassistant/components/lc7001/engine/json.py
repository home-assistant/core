"""A JSONable class that returns non-None properties."""

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


class Jsonable:
    """A JSONable class that returns non-None properties."""

    def asDict(self, log: bool | None = False) -> dict[str, Any]:
        """Return a the object as a dict without None values."""
        selfDict: dict[str, Any] = {}

        if log is True:
            _LOGGER.debug("JSON 0: %s", vars(self))

        for key, value in vars(self).items():
            if isinstance(value, Jsonable):
                selfDict[key] = value.asDict()
            elif isinstance(value, list):
                selfDict[key] = list(
                    value.asDict() if isinstance(value, Jsonable) else value
                )
            else:
                selfDict[key] = value

        if log is True:
            _LOGGER.debug("JSON 1: %s", selfDict)

        selfDict = {k: v for k, v in selfDict.items() if v is not None}

        if log is True:
            _LOGGER.debug("JSON 2: %s", selfDict)

        return selfDict
