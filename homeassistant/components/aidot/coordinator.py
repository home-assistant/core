"""Coordinator for Aidot."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type AidotConfigEntry = ConfigEntry[AidotCoordinator]


class AidotCoordinator:
    """Class to manage fetching Aidot data."""

    config_entry: AidotConfigEntry
    device_list: list[dict[str, Any]]
    login_response: dict[str, Any]
    product_list: list[dict[str, Any]]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AidotConfigEntry,
        device_list: list[dict[str, Any]],
        login_response: dict[str, Any],
        product_list: list[dict[str, Any]],
    ) -> None:
        """Initialize coordinator."""
        self.config_entry = config_entry
        self.identifier = config_entry.entry_id
        self.device_list = device_list
        self.login_response = login_response
        self.product_list = product_list
