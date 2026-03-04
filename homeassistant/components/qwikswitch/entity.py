"""Support for Qwikswitch devices."""

from __future__ import annotations

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DATA_QUIKSWITCH


class QSEntity(Entity):
    """Qwikswitch Entity base."""

    _attr_should_poll = False

    def __init__(self, qsid: str, name: str) -> None:
        """Initialize the QSEntity."""
        self._attr_name = name
        self._attr_unique_id = f"qs{qsid}"
        self.qsid = qsid

    @callback
    def update_packet(self, packet):
        """Receive update packet from QSUSB. Match dispather_send signature."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Listen for updates from QSUSb via dispatcher."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.qsid, self.update_packet)
        )


class QSToggleEntity(QSEntity):
    """Representation of a Qwikswitch Toggle Entity.

    Implemented:
     - QSLight extends QSToggleEntity and Light[2] (ToggleEntity[1])
     - QSSwitch extends QSToggleEntity and SwitchEntity[3] (ToggleEntity[1])

    [1] /helpers/entity.py
    [2] /components/light/__init__.py
    [3] /components/switch/__init__.py
    """

    def __init__(self, qsid, qsusb):
        """Initialize the ToggleEntity."""
        self.device = qsusb.devices[qsid]
        super().__init__(qsid, self.device.name)

    @property
    def is_on(self) -> bool:
        """Check if device is on (non-zero)."""
        return self.device.value > 0

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        new = kwargs.get(ATTR_BRIGHTNESS, 255)
        self.hass.data[DATA_QUIKSWITCH].devices.set_value(self.qsid, new)

    async def async_turn_off(self, **_):
        """Turn the device off."""
        self.hass.data[DATA_QUIKSWITCH].devices.set_value(self.qsid, 0)
