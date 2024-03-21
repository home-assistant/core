"""Support for Awair sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from python_awair.air_data import AirData
from python_awair.devices import AwairBaseDevice, AwairLocalDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_SW_VERSION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    API_CO2,
    API_DUST,
    API_HUMID,
    API_LUX,
    API_PM10,
    API_PM25,
    API_SCORE,
    API_SPL_A,
    API_TEMP,
    API_VOC,
    ATTRIBUTION,
    DOMAIN,
)
from .coordinator import AwairDataUpdateCoordinator, AwairResult

DUST_ALIASES = [API_PM25, API_PM10]


@dataclass(frozen=True, kw_only=True)
class AwairSensorEntityDescription(SensorEntityDescription):
    """Describes Awair sensor entity."""

    unique_id_tag: str


SENSOR_TYPE_SCORE = AwairSensorEntityDescription(
    key=API_SCORE,
    native_unit_of_measurement=PERCENTAGE,
    translation_key="score",
    unique_id_tag="score",  # matches legacy format
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_TYPES: tuple[AwairSensorEntityDescription, ...] = (
    AwairSensorEntityDescription(
        key=API_HUMID,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        unique_id_tag="HUMID",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        unique_id_tag="illuminance",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_SPL_A,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
        translation_key="sound_level",
        unique_id_tag="sound_level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_VOC,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        unique_id_tag="VOC",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        unique_id_tag="TEMP",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_CO2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        unique_id_tag="CO2",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSOR_TYPES_DUST: tuple[AwairSensorEntityDescription, ...] = (
    AwairSensorEntityDescription(
        key=API_PM25,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        unique_id_tag="PM25",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_PM10,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        unique_id_tag="PM10",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Awair sensor entity based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    data: list[AwairResult] = coordinator.data.values()
    for result in data:
        if result.air_data:
            entities.append(AwairSensor(result.device, coordinator, SENSOR_TYPE_SCORE))
            device_sensors = result.air_data.sensors.keys()
            entities.extend(
                [
                    AwairSensor(result.device, coordinator, description)
                    for description in (*SENSOR_TYPES, *SENSOR_TYPES_DUST)
                    if description.key in device_sensors
                ]
            )

            # The "DUST" sensor for Awair is a combo pm2.5/pm10 sensor only
            # present on first-gen devices in lieu of separate pm2.5/pm10 sensors.
            # We handle that by creating fake pm2.5/pm10 sensors that will always
            # report identical values, and we let users decide how they want to use
            # that data - because we can't really tell what kind of particles the
            # "DUST" sensor actually detected. However, it's still useful data.
            if API_DUST in device_sensors:
                entities.extend(
                    [
                        AwairSensor(result.device, coordinator, description)
                        for description in SENSOR_TYPES_DUST
                    ]
                )

    async_add_entities(entities)


class AwairSensor(CoordinatorEntity[AwairDataUpdateCoordinator], SensorEntity):
    """Defines an Awair sensor entity."""

    entity_description: AwairSensorEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        device: AwairBaseDevice,
        coordinator: AwairDataUpdateCoordinator,
        description: AwairSensorEntityDescription,
    ) -> None:
        """Set up an individual AwairSensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device

    @property
    def unique_id(self) -> str:
        """Return the uuid as the unique_id."""
        unique_id_tag = self.entity_description.unique_id_tag

        # This integration used to create a sensor that was labelled as a "PM2.5"
        # sensor for first-gen Awair devices, but its unique_id reflected the truth:
        # under the hood, it was a "DUST" sensor. So we preserve that specific unique_id
        # for users with first-gen devices that are upgrading.
        if (
            self.entity_description.key == API_PM25
            and self._air_data
            and API_DUST in self._air_data.sensors
        ):
            unique_id_tag = "DUST"

        return f"{self._device.uuid}_{unique_id_tag}"

    @property
    def available(self) -> bool:
        """Determine if the sensor is available based on API results."""
        # If the last update was successful...
        if self.coordinator.last_update_success and self._air_data:
            # and the results included our sensor type...
            sensor_type = self.entity_description.key
            if sensor_type in self._air_data.sensors:
                # then we are available.
                return True

            # or, we're a dust alias
            if sensor_type in DUST_ALIASES and API_DUST in self._air_data.sensors:
                return True

            # or we are API_SCORE
            if sensor_type == API_SCORE:
                # then we are available.
                return True

        # Otherwise, we are not.
        return False

    @property
    def native_value(self) -> float | None:
        """Return the state, rounding off to reasonable values."""
        if not self._air_data:
            return None

        state: float
        sensor_type = self.entity_description.key

        # Special-case for "SCORE", which we treat as the AQI
        if sensor_type == API_SCORE:
            state = self._air_data.score
        elif sensor_type in DUST_ALIASES and API_DUST in self._air_data.sensors:
            state = self._air_data.sensors.dust
        else:
            state = self._air_data.sensors[sensor_type]

        if sensor_type in {API_VOC, API_SCORE}:
            return round(state)

        if sensor_type == API_TEMP:
            return round(state, 1)

        return round(state, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the Awair Index alongside state attributes.

        The Awair Index is a subjective score ranging from 0-4 (inclusive) that
        is is used by the Awair app when displaying the relative "safety" of a
        given measurement. Each value is mapped to a color indicating the safety:

            0: green
            1: yellow
            2: light-orange
            3: orange
            4: red

        The API indicates that both positive and negative values may be returned,
        but the negative values are mapped to identical colors as the positive values.
        Knowing that, we just return the absolute value of a given index so that
        users don't have to handle positive/negative values that ultimately "mean"
        the same thing.

        https://docs.developer.getawair.com/?version=latest#awair-score-and-index
        """
        sensor_type = self.entity_description.key
        attrs: dict[str, Any] = {}
        if not self._air_data:
            return attrs
        if sensor_type in self._air_data.indices:
            attrs["awair_index"] = abs(self._air_data.indices[sensor_type])
        elif sensor_type in DUST_ALIASES and API_DUST in self._air_data.indices:
            attrs["awair_index"] = abs(self._air_data.indices.dust)

        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Device information."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._device.uuid)},
            manufacturer="Awair",
            model=self._device.model,
            name=(
                self._device.name
                or cast(ConfigEntry, self.coordinator.config_entry).title
                or f"{self._device.model} ({self._device.device_id})"
            ),
        )

        if self._device.mac_address:
            info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, self._device.mac_address)
            }

        if isinstance(self._device, AwairLocalDevice):
            info[ATTR_SW_VERSION] = self._device.fw_version

        return info

    @property
    def _air_data(self) -> AirData | None:
        """Return the latest data for our device, or None."""
        if result := self.coordinator.data.get(self._device.uuid):
            return result.air_data

        return None
