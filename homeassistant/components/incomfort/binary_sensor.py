"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an InComfort/InTouch binary_sensor device."""
    if discovery_info is None:
        return

    async_add_entities(
        [IncomfortFailed(hass.data[DOMAIN]["client"], hass.data[DOMAIN]["heater"])]
    )


class IncomfortFailed(BinarySensorDevice):
    """Representation of an InComfort Failed sensor."""

    def __init__(self, client, heater) -> None:
        """Initialize the binary sensor."""
        self._unique_id = f"{heater.serial_no}_failed"

        self._client = client
        self._heater = heater

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self) -> None:
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> Optional[str]:
        """Return the name of the sensor."""
        return "Fault state"

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return self._heater.status["is_failed"]

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the device state attributes."""
        return {"fault_code": self._heater.status["fault_code"]}

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False
