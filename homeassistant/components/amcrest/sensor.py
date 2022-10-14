"""Support for Amcrest IP camera sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from amcrest import AmcrestError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SENSORS, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICES, DOMAIN, SENSOR_SCAN_INTERVAL_SECS, SERVICE_UPDATE
from .helpers import log_update_error, service_signal

if TYPE_CHECKING:
    from . import AmcrestDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

SENSOR_PTZ_PRESET = "ptz_preset"
SENSOR_SDCARD = "sdcard"

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_PTZ_PRESET,
        name="PTZ Preset",
        icon="mdi:camera-iris",
    ),
    SensorEntityDescription(
        key=SENSOR_SDCARD,
        name="SD Used",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:sd",
    ),
)
SENSOR_KEYS = [description.key for description in SENSORS]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    sensors = config_entry.options.get(CONF_SENSORS, [])
    if sensors:
        name = config_entry.data[CONF_NAME]
        device = hass.data[DOMAIN][DEVICES][config_entry.entry_id]
        async_add_entities(
            (
                AmcrestSensor(name, device, description)
                for description in SENSORS
                if description.key in sensors
            ),
            True,
        )


class AmcrestSensor(SensorEntity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(
        self, name: str, device: AmcrestDevice, description: SensorEntityDescription
    ) -> None:
        """Initialize a sensor for Amcrest camera."""
        self.entity_description = description
        self._signal_name = name
        self._api = device.api
        self._channel = device.channel

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = (
            f"{device.serial_number}-{self.entity_description.key}-{self._channel}"
        )
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.available

    async def async_update(self) -> None:
        """Get the latest data and updates the state."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s sensor", self.name)

        sensor_type = self.entity_description.key

        try:
            if sensor_type == SENSOR_PTZ_PRESET:
                self._attr_native_value = await self._api.async_ptz_presets_count

            elif sensor_type == SENSOR_SDCARD:
                storage = await self._api.async_storage_all
                try:
                    self._attr_extra_state_attributes[
                        "Total"
                    ] = f"{storage['total'][0]:.2f} {storage['total'][1]}"
                except ValueError:
                    self._attr_extra_state_attributes[
                        "Total"
                    ] = f"{storage['total'][0]} {storage['total'][1]}"
                try:
                    self._attr_extra_state_attributes[
                        "Used"
                    ] = f"{storage['used'][0]:.2f} {storage['used'][1]}"
                except ValueError:
                    self._attr_extra_state_attributes[
                        "Used"
                    ] = f"{storage['used'][0]} {storage['used'][1]}"
                try:
                    self._attr_native_value = f"{storage['used_percent']:.2f}"
                except ValueError:
                    self._attr_native_value = storage["used_percent"]
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "sensor", error)

    async def async_added_to_hass(self) -> None:
        """Subscribe to update signal."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                service_signal(SERVICE_UPDATE, self._signal_name),
                self.async_write_ha_state,
            )
        )
