"""A generic abstract class which both PowersensorPlugs and PowersensorSensors subclass to share common methods."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Generic, TypeVar

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from ..const import DATA_UPDATE_SIGNAL_FMT_MAC_EVENT, DOMAIN, ROLE_UPDATE_SIGNAL
from .plug_measurements import PlugMeasurements
from .sensor_measurements import SensorMeasurements

_LOGGER = logging.getLogger(__name__)

MeasurementType = TypeVar("MeasurementType", SensorMeasurements, PlugMeasurements)


@dataclass(frozen=True, kw_only=True)
class PowersensorSensorEntityDescription(SensorEntityDescription):
    """Powersensor Sensor Entity Description."""

    conversion_function: Callable | None = None
    event: str | None = None
    message_key: str | None = None


class PowersensorEntity(SensorEntity, Generic[MeasurementType]):
    """Base class for all Powersensor entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        role: str,
        input_config: dict[MeasurementType, PowersensorSensorEntityDescription],
        measurement_type: MeasurementType,
        timeout_seconds: int = 60,
    ) -> None:
        """Initialize the sensor."""
        self._role = role
        self._has_recently_received_update_message = False
        self._attr_native_value = None
        self._attr_should_poll = False
        self._hass = hass
        self._mac = mac
        self._model = "PowersensorDevice"
        self._device_name = f"Powersensor Device (ID: {self._mac})"
        self._measurement_name: str | None = None
        self._remove_unavailability_tracker = None
        self._timeout = timedelta(seconds=timeout_seconds)  # Adjust as needed

        self.measurement_type: MeasurementType = measurement_type
        self.entity_description = input_config[measurement_type]
        config: PowersensorSensorEntityDescription = input_config[measurement_type]
        self.entity_description = config

        self._attr_unique_id = f"{mac}_{measurement_type.name}"
        self._attr_device_info = self.device_info

        self._signal = DATA_UPDATE_SIGNAL_FMT_MAC_EVENT % (mac, config.event)
        self._message_key = config.message_key
        self._message_callback = config.conversion_function

    @property
    def device_info(self) -> DeviceInfo:
        """Abstract property to for returning DeviceInfo."""
        raise NotImplementedError

    @property
    def available(self) -> bool:
        """Does data exist for this sensor type."""
        return self._has_recently_received_update_message

    def _schedule_unavailable(self):
        """Schedule entity to become unavailable."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()

        self._remove_unavailability_tracker = async_track_point_in_utc_time(
            self._hass, self._async_make_unavailable, utcnow() + self._timeout
        )

    async def _async_make_unavailable(self, _now):
        """Mark entity as unavailable."""
        self._has_recently_received_update_message = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to messages when added to home assistant."""
        self._has_recently_received_update_message = False
        self.async_on_remove(
            async_dispatcher_connect(self._hass, self._signal, self._handle_update)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, ROLE_UPDATE_SIGNAL, self._handle_role_update
            )
        )

    async def async_will_remove_from_hass(self):
        """Clean up."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()

    def _rename_based_on_role(self):
        return False

    @callback
    def _handle_role_update(self, mac: str, role: str | None) -> None:
        if self._mac != mac or self._role == role:
            return

        self._role = role
        name_updated = self._rename_based_on_role()

        if name_updated:
            device_registry = dr.async_get(self._hass)
            device = device_registry.async_get_device(identifiers={(DOMAIN, self._mac)})

            if device and device.name != self._device_name:
                # Update the device name
                device_registry.async_update_device(device.id, name=self._device_name)

            entity_registry = er.async_get(self._hass)
            entity_registry.async_update_entity(self.entity_id, name=self._attr_name)

            self.async_write_ha_state()

    @callback
    def _handle_update(self, event, message):
        """Handle pushed data."""

        # event is not presently used, but is passed to maintain flexibility for future development

        self._has_recently_received_update_message = True

        if self._message_key in message:
            if self._message_callback:
                self._attr_native_value = self._message_callback(
                    message[self._message_key]
                )
            else:
                self._attr_native_value = message[self._message_key]
        self._schedule_unavailable()

        self.async_write_ha_state()
