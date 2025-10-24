"""Switch for Orvibo Integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from orvibo.s20 import S20, S20Exception

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .repair import async_create_yaml_deprecation_issue

_LOGGER = logging.getLogger(__name__)


@dataclass
class S20Data:
    """S20 data class."""

    name: str
    host: str
    mac: str


type S20ConfigEntry = ConfigEntry[S20Data]

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the integration from configuration.yaml."""
    for switch in config.get("switches", []):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=switch,
            )
        )
        await async_create_yaml_deprecation_issue(
            hass,
            host=switch.get("host", "unknown"),
            mac=switch.get("mac", "unknown"),
            name=switch.get("name", "Unnamed Switch"),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S20ConfigEntry,
    async_add_entities,
) -> None:
    """Setup Entries."""
    switch = []
    switch.append(
        S20Switch(entry.data[CONF_NAME], entry.data[CONF_HOST], entry.data[CONF_MAC]),
    )
    async_add_entities(switch)


class S20Switch(SwitchEntity):
    """Representation of an S20 switch."""

    def __init__(self, name, host, mac):
        """Initialize the S20 device."""

        self._name = name
        self._host = host
        self._mac = mac
        self._state = False
        self._exc = S20Exception
        self._s20 = S20(self._host, self._mac)
        self._unique_id = "S20Switch_" + self._mac

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """Should poll."""
        return True

    @property
    def has_entity_name(self):
        """Has Entoty Name."""
        return True

    @property
    def unique_id(self):
        """Return Unique_ID."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._unique_id)
            },
            name=self._name,
            manufacturer="Orvibo",
            model="S20",
        )

    def _turn_on(self):
        try:
            self._s20.on = True
        except self._exc:
            _LOGGER.exception("Error while turning on S20")

    async def async_turn_on(self):
        """Turn the switch On."""
        await self.hass.async_add_executor_job(self._turn_on)

    def _turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        try:
            self._s20.on = False
        except self._exc:
            _LOGGER.exception("Error while turning off S20")

    async def async_turn_off(self):
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self._turn_off)

    def _update(self) -> None:
        """Update device state."""
        try:
            self._state = self._s20.on
        except self._exc:
            _LOGGER.exception("Error while fetching S20 state")

    async def async_update(self):
        """Update the switch status."""
        await self.hass.async_add_executor_job(self._update)
