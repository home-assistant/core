"""Utility functions for the KNX integration."""

from functools import partial
from typing import Any

from homeassistant.helpers.typing import ConfigType

from .const import CONF_DPT, CONF_GA_PASSIVE, CONF_GA_STATE, CONF_GA_WRITE


def nested_get(dic: ConfigType, *keys: str, default: Any | None = None) -> Any:
    """Get the value from a nested dictionary."""
    for key in keys:
        if key not in dic:
            return default
        dic = dic[key]
    return dic


class ConfigExtractor:
    """Helper class for extracting values from a knx config store dictionary."""

    __slots__ = ("get",)

    def __init__(self, config: ConfigType) -> None:
        """Initialize the extractor."""
        self.get = partial(nested_get, config)

    def get_write(self, *path: str) -> str | None:
        """Get the write group address."""
        return self.get(*path, CONF_GA_WRITE)  # type: ignore[no-any-return]

    def get_state(self, *path: str) -> str | None:
        """Get the state group address."""
        return self.get(*path, CONF_GA_STATE)  # type: ignore[no-any-return]

    def get_write_and_passive(self, *path: str) -> list[Any | None]:
        """Get the group addresses of write and passive."""
        write = self.get(*path, CONF_GA_WRITE)
        passive = self.get(*path, CONF_GA_PASSIVE)
        return [write, *passive] if passive else [write]

    def get_state_and_passive(self, *path: str) -> list[Any | None]:
        """Get the group addresses of state and passive."""
        state = self.get(*path, CONF_GA_STATE)
        passive = self.get(*path, CONF_GA_PASSIVE)
        return [state, *passive] if passive else [state]

    def get_dpt(self, *path: str) -> str | None:
        """Get the data point type of a group address config key."""
        return self.get(*path, CONF_DPT)  # type: ignore[no-any-return]
