"""Loads the BLUETTI integration's environment-specific application profile."""

import asyncio
import logging
import os
from typing import Any

import yaml

from homeassistant.core import HomeAssistant

from ..const import INTEGRATION_NAME

__LOGGER__ = logging.getLogger(__name__)


class ApplicationProfile:
    """The active application profile (server URLs, etc.) for this environment."""

    __active: str = ""
    __configFile: str = ""
    __configPath: str = ""

    def __init__(self, active: str | None = None) -> None:
        """Resolve which profile is active from the given value or the environment."""
        self.config: dict[str, Any] = {}
        self.__active = active or os.getenv("BLUETTI_PROFILE_ACTIVE", "").lower()
        __LOGGER__.info(
            "Setting up application profile: %s",
            "prod" if self.__active == "" else self.__active,
        )

        if self.__active != "":
            self.__active = "-" + self.__active

        self.__configFile = "application" + self.__active + ".yaml"
        self.__configPath = (
            os.path.dirname(os.path.abspath(__file__)) + "/" + self.__configFile
        )

    def load_config(self, hass: HomeAssistant) -> asyncio.Future[None]:
        """Load the active profile's YAML configuration file."""
        return hass.async_add_executor_job(self.__load_config)

    def __load_config(self) -> None:
        try:
            with open(self.__configPath, encoding="utf-8") as file:
                __yaml__ = yaml.safe_load(file)
        except (OSError, yaml.YAMLError) as err:
            __LOGGER__.error(
                "Failed to load profile %s of `%s` integration: %s",
                self.__configFile,
                INTEGRATION_NAME,
                err,
            )
            raise

        __LOGGER__.info(
            "Load profile %s of `%s` integration successfully.",
            self.__configFile,
            INTEGRATION_NAME,
        )
        self.config = __yaml__["bluetti"]


# The application profile. Was previously defined in api/bluetti.py, which
# moved to the pybluetti package; relocated here since this is where the
# class it instantiates lives.
APPLICATION_PROFILE = ApplicationProfile()
