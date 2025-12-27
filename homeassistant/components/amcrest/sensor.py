"""Support for Amcrest IP camera sensors."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from amcrest import AmcrestError

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SENSORS, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DATA_AMCREST, DEVICES, SENSOR_SCAN_INTERVAL_SECS, SERVICE_UPDATE
from .helpers import log_update_error, service_signal
from .models import AmcrestConfiguredDevice

if TYPE_CHECKING:
    from .models import AmcrestDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

SENSOR_PTZ_PRESET = "ptz_preset"
SENSOR_SDCARD = "sdcard"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
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

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    sensors = discovery_info[CONF_SENSORS]
    async_add_entities(
        [
            AmcrestSensor(name, device, description)
            for description in SENSOR_TYPES
            if description.key in sensors
        ],
        True,
    )


# Platform setup for config flow
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amcrest sensors for a config entry."""
    device = config_entry.runtime_data.device
    coordinator = config_entry.runtime_data.coordinator
    entities = [
        AmcrestCoordinatedSensor(device.name, device, coordinator, description)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities, True)


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
            if self._attr_unique_id is None and (
                serial_number := (await self._api.async_serial_number)
            ):
                self._attr_unique_id = f"{serial_number}-{sensor_type}-{self._channel}"

            if sensor_type == SENSOR_PTZ_PRESET:
                self._attr_native_value = await self._api.async_ptz_presets_count

            elif sensor_type == SENSOR_SDCARD:
                storage = await self._api.async_storage_all
                try:
                    self._attr_extra_state_attributes["Total"] = (
                        f"{storage['total'][0]:.2f} {storage['total'][1]}"
                    )
                except ValueError:
                    self._attr_extra_state_attributes["Total"] = (
                        f"{storage['total'][0]} {storage['total'][1]}"
                    )
                try:
                    self._attr_extra_state_attributes["Used"] = (
                        f"{storage['used'][0]:.2f} {storage['used'][1]}"
                    )
                except ValueError:
                    self._attr_extra_state_attributes["Used"] = (
                        f"{storage['used'][0]} {storage['used'][1]}"
                    )
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


class AmcrestCoordinatedSensor(CoordinatorEntity, AmcrestSensor):
    """Representation of an Amcrest Camera Sensor tied to DataUpdateCoordinator."""

    def __init__(
        self,
        name: str,
        device: AmcrestConfiguredDevice,
        coordinator: DataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        AmcrestSensor.__init__(self, name, device, entity_description)
        self._attr_device_info = device.device_info
        # Use serial number for unique ID if available, otherwise fall back to device name
        identifier = device.serial_number if device.serial_number else device.name
        self._attr_unique_id = f"{identifier}_{entity_description.key}"

    async def async_update(self) -> None:
        """Update the entity using coordinator data."""
        if not self.coordinator.last_update_success:
            return

        sensor_type = self.entity_description.key
        coordinator_data = self.coordinator.data

        try:
            if sensor_type == SENSOR_PTZ_PRESET:
                self._attr_native_value = coordinator_data.get("ptz_presets_count")

            elif sensor_type == SENSOR_SDCARD:
                storage = coordinator_data.get("storage_info")
                if storage is not None:
                    try:
                        self._attr_extra_state_attributes["Total"] = (
                            f"{storage['total'][0]:.2f} {storage['total'][1]}"
                        )
                    except (ValueError, KeyError, IndexError):
                        self._attr_extra_state_attributes["Total"] = (
                            f"{storage.get('total', ['N/A', 'N/A'])[0]} {storage.get('total', ['N/A', 'N/A'])[1]}"
                        )
                    try:
                        self._attr_extra_state_attributes["Used"] = (
                            f"{storage['used'][0]:.2f} {storage['used'][1]}"
                        )
                    except (ValueError, KeyError, IndexError):
                        self._attr_extra_state_attributes["Used"] = (
                            f"{storage.get('used', ['N/A', 'N/A'])[0]} {storage.get('used', ['N/A', 'N/A'])[1]}"
                        )
                    try:
                        self._attr_native_value = f"{storage['used_percent']:.2f}"
                    except (ValueError, KeyError):
                        # For numeric sensors, use None instead of "N/A" when data is unavailable
                        self._attr_native_value = None
                else:
                    # No storage data available - use None for numeric value
                    self._attr_extra_state_attributes["Total"] = "N/A"
                    self._attr_extra_state_attributes["Used"] = "N/A"
                    self._attr_native_value = None
        except (KeyError, TypeError, ValueError) as error:
            log_update_error(_LOGGER, "coordinator update", self.name, "sensor", error)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update sensor data based on coordinator data
        sensor_type = self.entity_description.key
        coordinator_data = self.coordinator.data

        try:
            if sensor_type == SENSOR_PTZ_PRESET:
                self._attr_native_value = coordinator_data.get("ptz_presets_count")

            elif sensor_type == SENSOR_SDCARD:
                storage = coordinator_data.get("storage_info")
                if storage is not None:
                    try:
                        self._attr_extra_state_attributes["Total"] = (
                            f"{storage['total'][0]:.2f} {storage['total'][1]}"
                        )
                    except (ValueError, KeyError, IndexError):
                        self._attr_extra_state_attributes["Total"] = (
                            f"{storage.get('total', ['N/A', 'N/A'])[0]} {storage.get('total', ['N/A', 'N/A'])[1]}"
                        )
                    try:
                        self._attr_extra_state_attributes["Used"] = (
                            f"{storage['used'][0]:.2f} {storage['used'][1]}"
                        )
                    except (ValueError, KeyError, IndexError):
                        self._attr_extra_state_attributes["Used"] = (
                            f"{storage.get('used', ['N/A', 'N/A'])[0]} {storage.get('used', ['N/A', 'N/A'])[1]}"
                        )
                    try:
                        # Handle case where used_percent might be "N/A" string
                        if (
                            storage["used_percent"] == "N/A"
                            or storage["used_percent"] is None
                        ):
                            self._attr_native_value = None
                        else:
                            self._attr_native_value = round(
                                float(storage["used_percent"]), 2
                            )
                    except (ValueError, KeyError, TypeError):
                        # For numeric sensors, use None instead of "N/A" when data is unavailable
                        self._attr_native_value = None
                else:
                    # No storage data available - use None for numeric value
                    self._attr_extra_state_attributes["Total"] = "N/A"
                    self._attr_extra_state_attributes["Used"] = "N/A"
                    self._attr_native_value = None
        except (KeyError, TypeError, ValueError) as error:
            log_update_error(_LOGGER, "coordinator update", self.name, "sensor", error)

        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data is not None
