"""Cover platform for Remootio."""

import logging
from typing import Any, override

from pyremootio import RemootioActionError, RemootioClient, RemootioError
from pyremootio.models import ActionErrorCode, DoorState, RemootioEvent

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RemootioConfigEntry
from .const import DOMAIN, device_name

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemootioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Remootio garage cover from a config entry."""
    async_add_entities([RemootioCover(entry)])


class RemootioCover(CoverEntity):
    """Garage door cover backed by a Remootio websocket client."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_should_poll = False

    def __init__(self, entry: RemootioConfigEntry) -> None:
        """Initialize the cover from the config entry's client."""
        self._client: RemootioClient = entry.runtime_data
        self._logged_unavailable = False
        assert entry.unique_id is not None
        serial = entry.unique_id
        self._serial = serial
        self._attr_unique_id = serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=device_name(serial),
            manufacturer="Remootio",
            model=self._client.remootio_version,
            serial_number=serial,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True while the client is authenticated."""
        return self._client.authenticated

    @property
    @override
    def assumed_state(self) -> bool:
        """Return True when the device has no door sensor."""
        return self._client.state in (DoorState.NO_SENSOR, DoorState.UNKNOWN)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return True if closed, False if open, None if unknown / no sensor."""
        match self._client.state:
            case DoorState.CLOSED:
                return True
            case DoorState.OPEN:
                return False
            case _:
                return None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to device events and connection changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.listen(self._async_on_event))
        self.async_on_remove(self._client.listen_connection(self._async_on_connection))

    @callback
    def _async_on_event(self, event: RemootioEvent) -> None:
        """Write HA state when the device pushes an event."""
        self.async_write_ha_state()

    @callback
    def _async_on_connection(self, connected: bool) -> None:
        """Write HA state on connect/disconnect; log once per drop and restore."""
        name = device_name(self._serial)
        if not connected:
            if not self._logged_unavailable:
                _LOGGER.info("Disconnected from %s", name)
                self._logged_unavailable = True
        elif self._logged_unavailable:
            _LOGGER.info("Reconnected to %s", name)
            self._logged_unavailable = False
        self.async_write_ha_state()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the door (falls back to a pulse if the device needs a sensor)."""
        await self._async_operate(opening=True)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the door (falls back to a pulse if the device needs a sensor)."""
        await self._async_operate(opening=False)

    async def _async_operate(self, *, opening: bool) -> None:
        """Send OPEN/CLOSE; impulse mode without a sensor rejects those with ERR_NO_SENSOR.

        Open/close output wiring can OPEN/CLOSE with no status sensor. Impulse
        wiring cannot; the device then returns ERR_NO_SENSOR and we pulse TRIGGER.
        The websocket API does not report which output mode is configured.
        """
        try:
            if opening:
                await self._client.open()
            else:
                await self._client.close()
        except RemootioActionError as err:
            if err.response.error_code != ActionErrorCode.NO_SENSOR:
                raise HomeAssistantError(str(err)) from err
            try:
                await self._client.trigger()
            except RemootioError as trigger_err:
                raise HomeAssistantError(str(trigger_err)) from trigger_err
        except RemootioError as err:
            raise HomeAssistantError(str(err)) from err
