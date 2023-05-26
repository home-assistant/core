"""Support for myStrom switches/plugs."""
from __future__ import annotations

import logging
from typing import Any

from pymystrom.exceptions import MyStromConnectionError
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_MANUFACTURER, DOMAIN

DEFAULT_NAME = "myStrom Switch"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the myStrom entities."""
    info = hass.data[DOMAIN][entry.entry_id].info
    device_type = info["type"]

    if device_type in [101, 106, 107]:
        device = hass.data[DOMAIN][entry.entry_id].device
        async_add_entities([MyStromSwitch(device)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the myStrom switch/plug integration."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


class MyStromSwitch(SwitchEntity):
    """Representation of a myStrom switch/plug."""

    def __init__(self, plug) -> None:
        """Initialize the myStrom switch/plug."""
        self.plug = plug
        self._available = True
        self.relay = None

    @property
    def name(self):
        """Return the name of the switch."""
        return self.plug.mac

    @property
    def is_on(self):
        """Return true if switch is on."""
        return bool(self.relay)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.plug.mac

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.plug.turn_on()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.plug.turn_off()
        except MyStromConnectionError:
            _LOGGER.error("No route to myStrom plug")

    async def async_update(self) -> None:
        """Get the latest data from the device and update the data."""
        try:
            await self.plug.get_state()
            self.relay = self.plug.relay
            self._available = True
        except MyStromConnectionError:
            if self._available:
                self._available = False
                _LOGGER.error("No route to myStrom plug")

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for the light entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.plug.mac)},
            name=self.name,
            manufacturer=ATTR_MANUFACTURER,
            sw_version=self.plug.firmware,
        )
