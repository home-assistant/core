"""Support for Onkyo Receivers."""

from __future__ import annotations

import logging

import eiscp

from homeassistant.components.media_player import DOMAIN
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BRAND_NAME

_LOGGER = logging.getLogger(__name__)


class TestEntity(SelectEntity):
    """Representation of an Onkyo device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_options = ["Optie een", "Optie twee"]
    _attr_current_option = "Optie een"

    def __init__(self, entry: ConfigEntry, receiver: eiscp.eISCP) -> None:
        """Initialize the Onkyo Receiver."""
        self._receiver = receiver

        self._attr_unique_id = str(entry.unique_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=BRAND_NAME,
            name=entry.data[CONF_NAME],
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Onkyo Platform from config_flow."""
    hosts: list[TestEntity] = []

    # host = entry.data[CONF_HOST]
    # try:
    #     receiver = eiscp.eISCP(host)
    #     hosts.append(
    #         TestEntity(
    #             entry,
    #             receiver,
    #         )
    #     )
    # except OSError:
    #     _LOGGER.error("Unable to connect to receiver at %s", host)
    #     raise
    # entry_data.async_remove_entities(
    #         hass, current_infos.values(), device_info.mac_address
    #     )

    async_add_entities(hosts)
