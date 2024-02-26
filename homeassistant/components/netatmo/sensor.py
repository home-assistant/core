"""Support for the Netatmo sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import cast

import pyatmo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import async_entries_for_config_entry
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_URL_ENERGY,
    CONF_URL_PUBLIC_WEATHER,
    CONF_URL_SECURITY,
    CONF_URL_WEATHER,
    CONF_WEATHER_AREAS,
    DATA_HANDLER,
    DOMAIN,
    EVENT_TYPE_DOOR_TAG_BIG_MOVE,
    EVENT_TYPE_DOOR_TAG_OPEN,
    EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
    EVENT_TYPE_HOME_ALARM,
    EVENT_TYPE_TAG_UNINSTALLED,
    NETATMO_CREATE_BATTERY,
    NETATMO_CREATE_OPENING_SENSOR,
    NETATMO_CREATE_ROOM_SENSOR,
    NETATMO_CREATE_SENSOR,
    NETATMO_CREATE_SIREN_SENSOR,
    NETATMO_CREATE_WEATHER_SENSOR,
    SIGNAL_NAME,
)
from .data_handler import HOME, PUBLIC, NetatmoDataHandler, NetatmoDevice, NetatmoRoom
from .entity import NetatmoBaseEntity
from .helper import NetatmoArea

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PUBLIC_SENSOR_TYPES: tuple[str, ...] = (
    "temperature",
    "pressure",
    "humidity",
    "rain",
    "wind_strength",
    "gust_strength",
    "sum_rain_1",
    "sum_rain_24",
    "wind_angle",
    "gust_angle",
)


@dataclass(frozen=True)
class NetatmoRequiredKeysMixin:
    """Mixin for required keys."""

    netatmo_name: str


@dataclass(frozen=True)
class NetatmoBinarySensorEntityDescription(
    BinarySensorEntityDescription, NetatmoRequiredKeysMixin
):
    """Describes Netatmo binary sensor entity."""


@dataclass(frozen=True)
class NetatmoSensorEntityDescription(SensorEntityDescription, NetatmoRequiredKeysMixin):
    """Describes Netatmo sensor entity."""


SENSOR_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="temperature",
        name="Temperature",
        netatmo_name="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    NetatmoSensorEntityDescription(
        key="temp_trend",
        name="Temperature trend",
        netatmo_name="temp_trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    NetatmoSensorEntityDescription(
        key="co2",
        name="CO2",
        netatmo_name="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO2,
    ),
    NetatmoSensorEntityDescription(
        key="pressure",
        name="Pressure",
        netatmo_name="pressure",
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    ),
    NetatmoSensorEntityDescription(
        key="pressure_trend",
        name="Pressure trend",
        netatmo_name="pressure_trend",
        entity_registry_enabled_default=False,
        icon="mdi:trending-up",
    ),
    NetatmoSensorEntityDescription(
        key="noise",
        name="Noise",
        netatmo_name="noise",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="humidity",
        name="Humidity",
        netatmo_name="humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    NetatmoSensorEntityDescription(
        key="rain",
        name="Rain",
        netatmo_name="rain",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_1",
        name="Rain last hour",
        netatmo_name="sum_rain_1",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL,
    ),
    NetatmoSensorEntityDescription(
        key="sum_rain_24",
        name="Rain today",
        netatmo_name="sum_rain_24",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    NetatmoSensorEntityDescription(
        key="battery_percent",
        name="Battery Percent",
        netatmo_name="battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    NetatmoSensorEntityDescription(
        key="windangle",
        name="Direction",
        netatmo_name="wind_direction",
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="windangle_value",
        name="Angle",
        netatmo_name="wind_angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="windstrength",
        name="Wind Strength",
        netatmo_name="wind_strength",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="gustangle",
        name="Gust Direction",
        netatmo_name="gust_direction",
        entity_registry_enabled_default=False,
        icon="mdi:compass-outline",
    ),
    NetatmoSensorEntityDescription(
        key="gustangle_value",
        name="Gust Angle",
        netatmo_name="gust_angle",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="guststrength",
        name="Gust Strength",
        netatmo_name="gust_strength",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetatmoSensorEntityDescription(
        key="reachable",
        name="Reachability",
        netatmo_name="reachable",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    NetatmoSensorEntityDescription(
        key="rf_status",
        name="Radio",
        netatmo_name="rf_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    NetatmoSensorEntityDescription(
        key="wifi_status",
        name="Wifi",
        netatmo_name="wifi_strength",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi",
    ),
    NetatmoSensorEntityDescription(
        key="health_idx",
        name="Health",
        netatmo_name="health_idx",
        icon="mdi:cloud",
    ),
    NetatmoSensorEntityDescription(
        key="power",
        name="Power",
        netatmo_name="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
)
SENSOR_TYPES_KEYS = [desc.key for desc in SENSOR_TYPES]

BATTERY_SENSOR_DESCRIPTION = NetatmoSensorEntityDescription(
    key="battery",
    name="Battery Percent",
    netatmo_name="battery",
    entity_category=EntityCategory.DIAGNOSTIC,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    device_class=SensorDeviceClass.BATTERY,
)

BINARY_SENSOR_SIREN_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="sounding",
        name="Sounding",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.SOUND,
        icon="mdi:alarm-light",
    ),
    NetatmoBinarySensorEntityDescription(
        key="monitoring",
        name="Monitoring",
        netatmo_name="monitoring",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:alarm-light",
    ),
)

SENSOR_SIREN_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="status",
        name="Status",
        netatmo_name="status",
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alarm-light",
        options=[
            "now_news",
            "no_sound",
            "warning",
            "sound",
            "playing_record_0",
            "playing_record_1",
            "playing_record_2",
            "playing_record_3",
        ],
    ),
)
BINARY_SENSOR_SIREN_TYPES_KEYS = [desc.key for desc in BINARY_SENSOR_SIREN_TYPES]
SENSOR_SIREN_TYPES_KEYS = [desc.key for desc in SENSOR_SIREN_TYPES]

BINARY_SENSOR_OPENING_TYPES: tuple[NetatmoBinarySensorEntityDescription, ...] = (
    NetatmoBinarySensorEntityDescription(
        key="opening",
        name="Opening",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:window-closed-variant",
    ),
    NetatmoBinarySensorEntityDescription(
        key="motion",
        name="Motion",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:window-closed-variant",
    ),
    NetatmoBinarySensorEntityDescription(
        key="vibration",
        name="Vibration",
        netatmo_name="status",
        device_class=BinarySensorDeviceClass.VIBRATION,
        icon="mdi:window-closed-variant",
    ),
)

SENSOR_OPENING_TYPES: tuple[NetatmoSensorEntityDescription, ...] = (
    NetatmoSensorEntityDescription(
        key="status",
        name="Status",
        netatmo_name="status",
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:window-closed-variant",
        options=[
            "no_news",
            "calibrating",
            "undefined",
            "closed",
            "open",
            "calibration_failed",
            "maintenance",
            "weak_signal",
        ],
    ),
)
BINARY_SENSOR_OPENING_TYPES_KEYS = [desc.key for desc in BINARY_SENSOR_OPENING_TYPES]
SENSOR_OPENING_TYPES_KEYS = [desc.key for desc in SENSOR_OPENING_TYPES]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Netatmo sensor platform."""

    @callback
    def _create_battery_entity(netatmo_device: NetatmoDevice) -> None:
        if not hasattr(netatmo_device.device, "battery"):
            return
        entity = NetatmoClimateBatterySensor(netatmo_device)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_BATTERY, _create_battery_entity)
    )

    @callback
    def _create_weather_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoWeatherSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_WEATHER_SENSOR, _create_weather_sensor_entity
        )
    )

    @callback
    def _create_siren_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoSirenSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )
        async_add_entities(
            NetatmoSirenBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_SIREN_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )
        async_add_entities(
            NetatmoSirenSensor(netatmo_device, description)
            for description in SENSOR_SIREN_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_SIREN_SENSOR, _create_siren_sensor_entity
        )
    )

    @callback
    def _create_opening_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        async_add_entities(
            NetatmoSirenSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )
        async_add_entities(
            NetatmoOpeningBinarySensor(netatmo_device, description)
            for description in BINARY_SENSOR_OPENING_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )
        async_add_entities(
            NetatmoOpeningSensor(netatmo_device, description)
            for description in SENSOR_OPENING_TYPES
            if description.netatmo_name in netatmo_device.device.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_OPENING_SENSOR, _create_opening_sensor_entity
        )
    )

    @callback
    def _create_sensor_entity(netatmo_device: NetatmoDevice) -> None:
        _LOGGER.debug(
            "Adding %s sensor %s",
            netatmo_device.device.device_category,
            netatmo_device.device.name,
        )
        async_add_entities(
            [
                NetatmoSensor(netatmo_device, description)
                for description in SENSOR_TYPES
                if description.key in netatmo_device.device.features
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_SENSOR, _create_sensor_entity)
    )

    @callback
    def _create_room_sensor_entity(netatmo_device: NetatmoRoom) -> None:
        if not netatmo_device.room.climate_type:
            msg = f"No climate type found for this room: {netatmo_device.room.name}"
            _LOGGER.debug(msg)
            return
        async_add_entities(
            NetatmoRoomSensor(netatmo_device, description)
            for description in SENSOR_TYPES
            if description.key in netatmo_device.room.features
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, NETATMO_CREATE_ROOM_SENSOR, _create_room_sensor_entity
        )
    )

    device_registry = dr.async_get(hass)
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    async def add_public_entities(update: bool = True) -> None:
        """Retrieve Netatmo public weather entities."""
        entities = {
            device.name: device.id
            for device in async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            if device.model == "Public Weather station"
        }

        new_entities = []
        for area in [
            NetatmoArea(**i) for i in entry.options.get(CONF_WEATHER_AREAS, {}).values()
        ]:
            signal_name = f"{PUBLIC}-{area.uuid}"

            if area.area_name in entities:
                entities.pop(area.area_name)

                if update:
                    async_dispatcher_send(
                        hass,
                        f"netatmo-config-{area.area_name}",
                        area,
                    )
                    continue

            await data_handler.subscribe(
                PUBLIC,
                signal_name,
                None,
                lat_ne=area.lat_ne,
                lon_ne=area.lon_ne,
                lat_sw=area.lat_sw,
                lon_sw=area.lon_sw,
                area_id=str(area.uuid),
            )

            new_entities.extend(
                [
                    NetatmoPublicSensor(data_handler, area, description)
                    for description in SENSOR_TYPES
                    if description.netatmo_name in SUPPORTED_PUBLIC_SENSOR_TYPES
                ]
            )

        for device_id in entities.values():
            device_registry.async_remove_device(device_id)

        async_add_entities(new_entities)

    async_dispatcher_connect(
        hass, f"signal-{DOMAIN}-public-update-{entry.entry_id}", add_public_entities
    )

    await add_public_entities(False)


class NetatmoWeatherSensor(NetatmoBaseEntity, SensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    _attr_has_entity_name = True
    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._station_id = (
            self._module.bridge if self._module.bridge is not None else self._id
        )
        self._device_name = self._module.name
        category = getattr(self._module.device_category, "name")
        self._publishers.extend(
            [
                {
                    "name": category,
                    SIGNAL_NAME: category,
                },
            ]
        )

        self._attr_name = f"{description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_WEATHER
        self._attr_unique_id = f"{self._id}-{description.key}"

        if hasattr(self._module, "place"):
            place = cast(
                pyatmo.modules.base_class.Place, getattr(self._module, "place")
            )
            if hasattr(place, "location") and place.location is not None:
                self._attr_extra_state_attributes.update(
                    {
                        ATTR_LATITUDE: place.location.latitude,
                        ATTR_LONGITUDE: place.location.longitude,
                    }
                )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if (
            not self._module.reachable
            or (state := getattr(self._module, self.entity_description.netatmo_name))
            is None
        ):
            if self.available:
                self._attr_available = False
            return

        if self.entity_description.netatmo_name in {
            "temperature",
            "pressure",
            "sum_rain_1",
        }:
            self._attr_native_value = round(state, 1)
        elif self.entity_description.netatmo_name == "rf_strength":
            self._attr_native_value = process_rf(state)
        elif self.entity_description.netatmo_name == "wifi_strength":
            self._attr_native_value = process_wifi(state)
        elif self.entity_description.netatmo_name == "health_idx":
            self._attr_native_value = process_health(state)
        else:
            self._attr_native_value = state

        self._attr_available = True
        self.async_write_ha_state()


class NetatmoClimateBatterySensor(NetatmoBaseEntity, SensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = BATTERY_SENSOR_DESCRIPTION

        self._module = cast(pyatmo.modules.NRV, netatmo_device.device)
        self._id = netatmo_device.parent_id

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

        self._attr_name = f"{self._module.name} {self.entity_description.name}"
        self._room_id = self._module.room_id
        self._model = getattr(self._module.device_type, "value")
        self._config_url = CONF_URL_ENERGY

        self._attr_unique_id = (
            f"{self._id}-{self._module.entity_id}-{self.entity_description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = self._module.battery


class NetatmoSirenBinarySensor(NetatmoBaseEntity, BinarySensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    _attr_has_entity_name = True
    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._bridge = self._module.bridge if self._module.bridge is not None else None
        self._device_name = self._module.name
        self._signal_name = netatmo_device.signal_name
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._attr_name = f"{description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_SECURITY
        self._attr_unique_id = f"{self._id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        if (
            state := getattr(self._module, self.entity_description.netatmo_name)
        ) is None:
            return

        if self.entity_description.key == "sounding":
            self._attr_available = True
            if state in ("no_sound", "now_news", "warning"):
                self.is_on = False
            else:
                self.is_on = True
        elif self.entity_description.key == "monitoring":
            self._attr_available = True
            self.is_on = state
        else:
            self._attr_available = False

        self.async_write_ha_state()

    @callback
    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        if self.entity_description.key == "sounding":
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{EVENT_TYPE_HOME_ALARM}",
                    self.handle_event,
                )
            )

    @callback
    async def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        _LOGGER.debug(
            "receive event %s on  %s and %s",
            event["type"],
            self._device_name,
            self.entity_description.key,
        )
        if event["type"] == EVENT_TYPE_HOME_ALARM:
            if event["data"]["device_id"] == self._bridge:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    EVENT_TYPE_HOME_ALARM,
                    self._device_name,
                    self.entity_description.key,
                )
                self.data_handler.async_force_update(self._signal_name)
        else:
            _LOGGER.debug(
                "handle_event %s on  %s and %s not supported",
                event["type"],
                self._device_name,
                self.entity_description.key,
            )


class NetatmoSirenSensor(NetatmoBaseEntity, SensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    _attr_has_entity_name = True
    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._bridge = self._module.bridge if self._module.bridge is not None else None
        self._device_name = self._module.name
        self._signal_name = netatmo_device.signal_name
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._attr_name = f"{description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_SECURITY
        self._attr_unique_id = f"{self._id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        if (
            state := getattr(self._module, self.entity_description.netatmo_name)
        ) is None:
            return

        if self.entity_description.netatmo_name == "rf_strength":
            self._attr_native_value = process_rf(state)
        elif self.entity_description.netatmo_name == "wifi_strength":
            self._attr_native_value = process_wifi(state)
        else:
            self._attr_native_value = state

        self._attr_available = True
        self.async_write_ha_state()


class NetatmoOpeningBinarySensor(NetatmoBaseEntity, BinarySensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    _attr_has_entity_name = True
    entity_description: NetatmoBinarySensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._bridge = self._module.bridge if self._module.bridge is not None else None
        self._device_name = self._module.name
        self._signal_name = netatmo_device.signal_name
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._attr_name = f"{description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_SECURITY
        self._attr_unique_id = f"{self._id}-{description.key}"
        self._hasEvent = False

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        if (
            state := getattr(self._module, self.entity_description.netatmo_name)
        ) is None:
            return

        if self.entity_description.key == "opening":
            self._attr_available = True
            if state == "open":
                self.is_on = True
            elif state == "closed":
                self.is_on = False
            else:
                self._attr_available = False
                self.is_on = None
        elif self.entity_description.key == "motion":
            self._attr_available = True
            self.is_on = False
        elif self.entity_description.key == "vibration":
            self._attr_available = True
            self.is_on = False
        else:
            self._attr_available = False
            self.is_on = None

        self.async_write_ha_state()

    @callback
    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        for event_type in (
            EVENT_TYPE_DOOR_TAG_OPEN,
            EVENT_TYPE_TAG_UNINSTALLED,
        ):
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"signal-{DOMAIN}-webhook-{event_type}",
                    self.handle_event,
                )
            )
        if self.entity_description.key in ("motion", "vibration"):
            for event_type in (
                EVENT_TYPE_DOOR_TAG_BIG_MOVE,
                EVENT_TYPE_DOOR_TAG_SMALL_MOVE,
            ):
                self.async_on_remove(
                    async_dispatcher_connect(
                        self.hass,
                        f"signal-{DOMAIN}-webhook-{event_type}",
                        self.handle_event,
                    )
                )

    @callback
    async def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        _LOGGER.debug(
            "receive event %s on  %s and %s",
            event["type"],
            self._device_name,
            self.entity_description.key,
        )
        if event["type"] == EVENT_TYPE_DOOR_TAG_OPEN:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    EVENT_TYPE_DOOR_TAG_OPEN,
                    self._device_name,
                    self.entity_description.key,
                )
                state = True
                if self.entity_description.key in ("motion", "vibration"):
                    state = False
                self.is_on = state
                self._attr_available = True
                self.async_write_ha_state()
        elif event["type"] == EVENT_TYPE_DOOR_TAG_BIG_MOVE:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    event["type"],
                    self._device_name,
                    self.entity_description.key,
                )
                state = True
                if self.entity_description.key == "vibration":
                    state = False
                self.is_on = state
                self._attr_available = True
                self.async_write_ha_state()
        elif event["type"] == EVENT_TYPE_DOOR_TAG_SMALL_MOVE:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    event["type"],
                    self._device_name,
                    self.entity_description.key,
                )
                state = True
                if self.entity_description.key == "motion":
                    state = False
                self.is_on = state
                self._attr_available = True
                self.async_write_ha_state()
        elif event["type"] == EVENT_TYPE_TAG_UNINSTALLED:
            if event["data"]["module_id"] == self._id:
                _LOGGER.debug(
                    "handle_event %s on  %s and %s",
                    EVENT_TYPE_DOOR_TAG_OPEN,
                    self._device_name,
                    self.entity_description.key,
                )
                self.is_on = None
                self._attr_available = False
                self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "handle_event %s on  %s and %s not supported",
                event["type"],
                self._device_name,
                self.entity_description.key,
            )


class NetatmoOpeningSensor(NetatmoBaseEntity, SensorEntity):
    """Implementation of a Netatmo weather/home coach sensor."""

    _attr_has_entity_name = True
    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id
        self._bridge = self._module.bridge if self._module.bridge is not None else None
        self._device_name = self._module.name
        self._signal_name = netatmo_device.signal_name
        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: self._signal_name,
                },
            ]
        )

        self._attr_name = f"{description.name}"
        self._model = self._module.device_type
        self._config_url = CONF_URL_SECURITY
        self._attr_unique_id = f"{self._id}-{description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        if (
            state := getattr(self._module, self.entity_description.netatmo_name)
        ) is None:
            return

        if self.entity_description.netatmo_name == "rf_strength":
            self._attr_native_value = process_rf(state)
        elif self.entity_description.netatmo_name == "wifi_strength":
            self._attr_native_value = process_wifi(state)
        else:
            self._attr_native_value = state

        self._attr_available = True
        self.async_write_ha_state()


class NetatmoSensor(NetatmoBaseEntity, SensorEntity):
    """Implementation of a Netatmo sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_device: NetatmoDevice,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_device.data_handler)
        self.entity_description = description

        self._module = netatmo_device.device
        self._id = self._module.entity_id

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_device.device.home.entity_id,
                    SIGNAL_NAME: netatmo_device.signal_name,
                },
            ]
        )

        self._attr_name = f"{self._module.name} {self.entity_description.name}"
        self._room_id = self._module.room_id
        self._model = getattr(self._module.device_type, "value")
        self._config_url = CONF_URL_ENERGY

        self._attr_unique_id = (
            f"{self._id}-{self._module.entity_id}-{self.entity_description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if not self._module.reachable:
            if self.available:
                self._attr_available = False
            return

        if (state := getattr(self._module, self.entity_description.key)) is None:
            return

        self._attr_available = True
        self._attr_native_value = state

        self.async_write_ha_state()


def process_health(health: int) -> str:
    """Process health index and return string for display."""
    if health == 0:
        return "Healthy"
    if health == 1:
        return "Fine"
    if health == 2:
        return "Fair"
    if health == 3:
        return "Poor"
    return "Unhealthy"


def process_rf(strength: int) -> str:
    """Process wifi signal strength and return string for display."""
    if strength >= 90:
        return "Low"
    if strength >= 76:
        return "Medium"
    if strength >= 60:
        return "High"
    return "Full"


def process_wifi(strength: int) -> str:
    """Process wifi signal strength and return string for display."""
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"


class NetatmoRoomSensor(NetatmoBaseEntity, SensorEntity):
    """Implementation of a Netatmo room sensor."""

    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        netatmo_room: NetatmoRoom,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(netatmo_room.data_handler)
        self.entity_description = description

        self._room = netatmo_room.room
        self._id = self._room.entity_id

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": netatmo_room.room.home.entity_id,
                    SIGNAL_NAME: netatmo_room.signal_name,
                },
            ]
        )

        self._attr_name = f"{self._room.name} {self.entity_description.name}"
        self._room_id = self._room.entity_id
        self._config_url = CONF_URL_ENERGY

        assert self._room.climate_type
        self._model = self._room.climate_type

        self._attr_unique_id = (
            f"{self._id}-{self._room.entity_id}-{self.entity_description.key}"
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        if (state := getattr(self._room, self.entity_description.key)) is None:
            return

        self._attr_native_value = state

        self.async_write_ha_state()


class NetatmoPublicSensor(NetatmoBaseEntity, SensorEntity):
    """Represent a single sensor in a Netatmo."""

    _attr_has_entity_name = True
    entity_description: NetatmoSensorEntityDescription

    def __init__(
        self,
        data_handler: NetatmoDataHandler,
        area: NetatmoArea,
        description: NetatmoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_handler)
        self.entity_description = description

        self._signal_name = f"{PUBLIC}-{area.uuid}"
        self._publishers.append(
            {
                "name": PUBLIC,
                "lat_ne": area.lat_ne,
                "lon_ne": area.lon_ne,
                "lat_sw": area.lat_sw,
                "lon_sw": area.lon_sw,
                "area_name": area.area_name,
                SIGNAL_NAME: self._signal_name,
            }
        )

        self._station = data_handler.account.public_weather_areas[str(area.uuid)]

        self.area = area
        self._mode = area.mode
        self._area_name = area.area_name
        self._id = self._area_name
        self._device_name = f"{self._area_name}"
        self._attr_name = f"{description.name}"
        self._show_on_map = area.show_on_map
        self._config_url = CONF_URL_PUBLIC_WEATHER
        self._attr_unique_id = (
            f"{self._device_name.replace(' ', '-')}-{description.key}"
        )
        self._model = PUBLIC

        self._attr_extra_state_attributes.update(
            {
                ATTR_LATITUDE: (self.area.lat_ne + self.area.lat_sw) / 2,
                ATTR_LONGITUDE: (self.area.lon_ne + self.area.lon_sw) / 2,
            }
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        assert self.device_info and "name" in self.device_info
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"netatmo-config-{self.device_info['name']}",
                self.async_config_update_callback,
            )
        )

    async def async_config_update_callback(self, area: NetatmoArea) -> None:
        """Update the entity's config."""
        if self.area == area:
            return

        await self.data_handler.unsubscribe(
            self._signal_name, self.async_update_callback
        )

        self.area = area
        self._signal_name = f"{PUBLIC}-{area.uuid}"
        self._mode = area.mode
        self._show_on_map = area.show_on_map
        await self.data_handler.subscribe(
            PUBLIC,
            self._signal_name,
            self.async_update_callback,
            lat_ne=area.lat_ne,
            lon_ne=area.lon_ne,
            lat_sw=area.lat_sw,
            lon_sw=area.lon_sw,
        )

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        data = None

        if self.entity_description.netatmo_name == "temperature":
            data = self._station.get_latest_temperatures()
        elif self.entity_description.netatmo_name == "pressure":
            data = self._station.get_latest_pressures()
        elif self.entity_description.netatmo_name == "humidity":
            data = self._station.get_latest_humidities()
        elif self.entity_description.netatmo_name == "rain":
            data = self._station.get_latest_rain()
        elif self.entity_description.netatmo_name == "sum_rain_1":
            data = self._station.get_60_min_rain()
        elif self.entity_description.netatmo_name == "sum_rain_24":
            data = self._station.get_24_h_rain()
        elif self.entity_description.netatmo_name == "wind_strength":
            data = self._station.get_latest_wind_strengths()
        elif self.entity_description.netatmo_name == "gust_strength":
            data = self._station.get_latest_gust_strengths()
        elif self.entity_description.netatmo_name == "wind_angle":
            data = self._station.get_latest_wind_angles()
        elif self.entity_description.netatmo_name == "gust_angle":
            data = self._station.get_latest_gust_angles()

        if not data:
            if self.available:
                _LOGGER.error(
                    "No station provides %s data in the area %s",
                    self.entity_description.key,
                    self._area_name,
                )

            self._attr_available = False
            return

        if values := [x for x in data.values() if x is not None]:
            if self._mode == "avg":
                self._attr_native_value = round(sum(values) / len(values), 1)
            elif self._mode == "max":
                self._attr_native_value = max(values)

        self._attr_available = self.state is not None
        self.async_write_ha_state()
