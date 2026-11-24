"""The Ecowitt Weather Station Entity."""

from datetime import datetime
from typing import override

from aioecowitt import EcoWittSensor

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

# The gateway stops sending data for sensors it no longer receives from.
# Just over the longest upload interval a gateway can be configured with.
UNAVAILABLE_TIMEOUT = 11 * 60


class EcowittEntity(Entity):
    """Base class for Ecowitt Weather Station."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, sensor: EcoWittSensor) -> None:
        """Construct the entity."""
        self.ecowitt: EcoWittSensor = sensor
        self._cancel_unavailable: CALLBACK_TYPE | None = None

        self._attr_unique_id = f"{sensor.station.key}-{sensor.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor.station.key)},
            name=sensor.station.model,
            model=sensor.station.model,
            manufacturer="Ecowitt",
            sw_version=sensor.station.version,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Install listener for updates later."""

        @callback
        def _update_state() -> None:
            """Update the state on callback."""
            self._attr_available = True
            self._async_schedule_unavailable()
            self.async_write_ha_state()

        self.ecowitt.update_cb.append(_update_state)
        self.async_on_remove(lambda: self.ecowitt.update_cb.remove(_update_state))
        self.async_on_remove(self._async_cancel_unavailable)
        self._async_schedule_unavailable()

    @callback
    def _async_schedule_unavailable(self) -> None:
        """(Re)start the timer that marks the entity unavailable."""
        self._async_cancel_unavailable()
        self._cancel_unavailable = async_call_later(
            self.hass, UNAVAILABLE_TIMEOUT, self._async_mark_unavailable
        )

    @callback
    def _async_cancel_unavailable(self) -> None:
        """Cancel the unavailable timer."""
        if self._cancel_unavailable is not None:
            self._cancel_unavailable()
            self._cancel_unavailable = None

    @callback
    def _async_mark_unavailable(self, _now: datetime) -> None:
        """Mark the entity unavailable after not receiving data."""
        self._cancel_unavailable = None
        self._attr_available = False
        self.async_write_ha_state()
