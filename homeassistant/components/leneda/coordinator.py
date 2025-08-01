"""The Leneda coordinator for handling meter data and statistics."""

from __future__ import annotations

import logging
import re
from typing import Any

from leneda import LenedaClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _create_statistic_id(metering_point: str, obis: str) -> str:
    """Create a valid statistic ID from metering point and OBIS code.

    Args:
        metering_point: The metering point identifier
        obis: The OBIS code

    Returns:
        A formatted statistic ID string

    """
    clean_mp = re.sub(r"[^a-z0-9]", "_", metering_point.lower())
    clean_obis = re.sub(r"[^a-z0-9]", "_", obis.lower())
    statistic_id = f"{DOMAIN}:{clean_mp}_{clean_obis}"
    _LOGGER.debug(
        "Created statistic ID: %s from metering_point: %s, obis: %s",
        statistic_id,
        metering_point,
        obis,
    )
    return statistic_id


class LenedaCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Handle fetching Leneda data, updating sensors and inserting statistics."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_token: str,
        energy_id: str,
    ) -> None:
        """Initialize the coordinator for all metering point subentries.

        Args:
            hass: Home Assistant instance
            config_entry: Configuration entry
            api_token: API token for authentication
            energy_id: Energy ID for the client

        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = LenedaClient(
            api_key=api_token,
            energy_id=energy_id,
        )
