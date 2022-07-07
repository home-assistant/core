"""IMAP sensor support."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImapDataUpdateCoordinator
from .const import (
    CONF_CHARSET,
    CONF_FOLDER,
    CONF_SEARCH,
    CONF_SERVER,
    DEFAULT_PORT,
    DOMAIN,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SERVER): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_CHARSET, default="utf-8"): cv.string,
        vol.Optional(CONF_FOLDER, default="INBOX"): cv.string,
        vol.Optional(CONF_SEARCH, default="UnSeen UnDeleted"): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the IMAP platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )

    _LOGGER.warning(
        "IMAP sensor platform configuration has been imported into the UI. "
        "Please remove it from configuration.yaml as it will be "
        "removed in a future release"
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Imap sensor."""

    coordinator: ImapDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([ImapSensor(coordinator)])


class ImapSensor(CoordinatorEntity[ImapDataUpdateCoordinator], SensorEntity):
    """Representation of an IMAP sensor."""

    _attr_icon = "mdi:email-outline"

    def __init__(self, coordinator: ImapDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = coordinator.entry.data[CONF_NAME]
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}-{coordinator.entry.data[CONF_USERNAME]}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.data[CONF_NAME],
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        """Return the number of emails found."""
        return self.coordinator.data
