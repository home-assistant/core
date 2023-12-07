"""Switch implementation for EGPS Platform."""

from typing import Any

from pyegps import __version__ as PYEGPS_VERSION
from pyegps.exceptions import EgpsException
from pyegps.powerstrip import PowerStrip

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add EGPS sockets for passed config_entry in HA."""
    powerstrip: PowerStrip = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        EGPowerStripSocket(powerstrip, socket)
        for socket in range(powerstrip.numberOfSockets)
    )


class EGPowerStripSocket(SwitchEntity):
    """Represents a socket of an Energenie-Socket-Strip."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, dev: PowerStrip, socket: int) -> None:
        """Initiate a new socket."""
        self._dev = dev
        self._socket = socket
        self._state = STATE_OFF

    @property
    def unique_id(self) -> str:
        """Return the unique id for a socket."""
        return f"{self._dev.device_id}_{self._socket}"

    @property
    def name(self) -> str:
        """Return the display name of this socket."""
        return f"{self._dev.name} Socket {self._socket}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._dev.device_id)},
            name=f"{self._dev.name} ({self._dev.device_id})",
            manufacturer=self._dev.manufacturer,
            model=self._dev.name,
            sw_version=PYEGPS_VERSION,
        )

    @property
    def is_on(self) -> bool:
        """Return True if socket is on, else False."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        """Switch the socket on."""
        self._dev.switch_on(self._socket)

    def turn_off(self, **kwargs: Any) -> None:
        """Switch the socket off."""
        self._dev.switch_off(self._socket)

    @property
    def should_poll(self) -> bool:
        """Return True, as this device uses polling."""
        return True

    def update(self) -> None:
        """Read the current state from the device."""
        try:
            self._state = STATE_ON if self._dev.get_status(self._socket) else STATE_OFF
        except EgpsException as err:
            LOGGER.error("Unable to fetch data: %s", err)
