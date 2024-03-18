"""Switch implementation for EGPS Platform."""

from typing import Any

from pyegps import __version__ as PYEGPS_VERSION
from pyegps.exceptions import EgpsException
from pyegps.powerstrip import PowerStrip

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


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
    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(self, dev: PowerStrip, socket: int) -> None:
        """Initiate a new socket."""
        self._dev = dev
        self._socket = socket
        self._state = STATE_OFF

        self._attr_name = f"Socket {socket}"

        self._attr_unique_id = f"{dev.device_id}_{socket}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev.device_id)},
            name=dev.name,
            manufacturer=dev.manufacturer,
            model=dev.name,
            sw_version=PYEGPS_VERSION,
        )

    @property
    def is_on(self) -> bool:
        """Return True if socket is on, else False."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs: Any) -> None:
        """Switch the socket on."""
        try:
            self._dev.switch_on(self._socket)
        except EgpsException as err:
            raise HomeAssistantError(f"Couldn't access USB device: {err}") from err

    def turn_off(self, **kwargs: Any) -> None:
        """Switch the socket off."""
        try:
            self._dev.switch_off(self._socket)
        except EgpsException as err:
            raise HomeAssistantError(f"Couldn't access USB device: {err}") from err

    def update(self) -> None:
        """Read the current state from the device."""
        try:
            self._state = STATE_ON if self._dev.get_status(self._socket) else STATE_OFF
        except EgpsException as err:
            raise HomeAssistantError(f"Couldn't access USB device: {err}") from err
