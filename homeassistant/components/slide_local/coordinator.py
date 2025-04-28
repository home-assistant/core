"""DataUpdateCoordinator for slide_local integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from goslideapi.goslideapi import (
    AuthenticationFailed,
    ClientConnectionError,
    ClientTimeoutError,
    DigestAuthCalcError,
    GoSlideLocal as SlideLocalApi,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_OFFSET, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SlideConfigEntry = ConfigEntry[SlideCoordinator]


class SlideCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Get and update the latest data."""

    config_entry: SlideConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SlideConfigEntry) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Slide",
            update_interval=timedelta(seconds=15),
        )
        self.slide = SlideLocalApi()
        self.api_version = config_entry.data[CONF_API_VERSION]
        self.mac = config_entry.data[CONF_MAC]
        self.host = config_entry.data[CONF_HOST]
        self.password = (
            config_entry.data[CONF_PASSWORD] if self.api_version == 1 else ""
        )

    async def _async_setup(self) -> None:
        """Do initialization logic for Slide coordinator."""
        _LOGGER.debug("Initializing Slide coordinator")

        await self.slide.slide_add(
            self.host,
            self.password,
            self.api_version,
        )

        _LOGGER.debug("Slide coordinator initialized")

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the data from the Slide device."""
        _LOGGER.debug("Start data update")

        try:
            data = await self.slide.slide_info(self.host)
        except (
            ClientConnectionError,
            AuthenticationFailed,
            ClientTimeoutError,
            DigestAuthCalcError,
        ) as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
            ) from ex

        if data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
            )

        if "pos" in data:
            if self.data is None:
                oldpos = None
            else:
                oldpos = self.data.get("pos")

            data["pos"] = max(0, min(1, data["pos"]))

            if oldpos is None or oldpos == data["pos"]:
                data["state"] = (
                    STATE_CLOSED if data["pos"] > (1 - DEFAULT_OFFSET) else STATE_OPEN
                )
            elif oldpos < data["pos"]:
                data["state"] = (
                    STATE_CLOSED
                    if data["pos"] >= (1 - DEFAULT_OFFSET)
                    else STATE_CLOSING
                )
            else:
                data["state"] = (
                    STATE_OPEN if data["pos"] <= DEFAULT_OFFSET else STATE_OPENING
                )

        _LOGGER.debug("Data successfully updated: %s", data)

        return data
