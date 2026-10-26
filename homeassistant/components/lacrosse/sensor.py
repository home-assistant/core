"""Support for LaCrosse sensor components."""

from datetime import datetime, timedelta
import logging
from typing import Any, override

import probatio
import pylacrosse

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_DEVICE,
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TYPE,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import LaCrosseConfigEntry
from .const import (
    CONF_BAUD,
    CONF_DATARATE,
    CONF_EXPIRE_AFTER,
    CONF_FREQUENCY,
    CONF_JEELINK_LED,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
    DEFAULT_BAUD,
    DEFAULT_EXPIRE_AFTER,
    DOMAIN,
    TYPES,
    sensor_entity_key,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ID): cv.positive_int,
        probatio.Required(CONF_TYPE): probatio.In(TYPES),
        probatio.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
        probatio.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
        probatio.Optional(CONF_BAUD, default=DEFAULT_BAUD): cv.positive_int,
        probatio.Optional(CONF_DATARATE): cv.positive_int,
        probatio.Optional(CONF_DEVICE): cv.string,
        probatio.Optional(CONF_FREQUENCY): cv.positive_int,
        probatio.Optional(CONF_JEELINK_LED): cv.boolean,
        probatio.Optional(CONF_TOGGLE_INTERVAL): cv.positive_int,
        probatio.Optional(CONF_TOGGLE_MASK): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaCrosseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaCrosse sensors from a config entry."""
    for subentry in entry.subentries.values():
        sensors = {
            sensor_entity_key(subentry.subentry_id, sensor[CONF_TYPE])
            if key == sensor[CONF_TYPE]
            else key: sensor
            for key, sensor in subentry.data[CONF_SENSORS].items()
        }
        _add_sensors(
            hass,
            entry.runtime_data,
            entry.entry_id,
            {**entry.data, **subentry.data, CONF_SENSORS: sensors},
            lambda entities, subentry_id=subentry.subentry_id: async_add_entities(
                entities, config_subentry_id=subentry_id
            ),
        )


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the LaCrosse sensors through the legacy YAML import flow."""
    hass.add_job(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


def _add_sensors(
    hass: HomeAssistant,
    lacrosse: pylacrosse.LaCrosse,
    receiver_entry_id: str,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
) -> None:
    """Create entities for the configured LaCrosse sensors."""
    sensors: list[LaCrosseSensor] = []
    for device, device_config in config[CONF_SENSORS].items():
        _LOGGER.debug("%s %s", device, device_config)

        typ: str = device_config[CONF_TYPE]
        sensor_class = TYPE_CLASSES[typ]
        name = typ.capitalize()
        expire_after: int | None = device_config.get(
            CONF_EXPIRE_AFTER, DEFAULT_EXPIRE_AFTER
        )
        sensors.append(
            sensor_class(
                hass,
                lacrosse,
                receiver_entry_id,
                config[CONF_DEVICE],
                device,
                name,
                expire_after,
                device_config,
            )
        )

    add_entities(sensors)


def sensor_device_name(config: ConfigType) -> str:
    """Return the configured or default sensor device name."""
    if (
        isinstance(friendly_name := config.get(CONF_FRIENDLY_NAME), str)
        and friendly_name.strip()
    ):
        return friendly_name
    return f"LaCrosse sensor {config[CONF_ID]}"


class LaCrosseSensor(SensorEntity):
    """Implementation of a Lacrosse sensor."""

    _temperature: float | None = None
    _humidity: int | None = None
    _low_battery: bool | None = None
    _new_battery: bool | None = None
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        lacrosse: pylacrosse.LaCrosse,
        receiver_entry_id: str,
        receiver_device: str,
        device_id: str,
        name: str,
        expire_after: int | None,
        config: ConfigType,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._config = config
        self._expire_after = expire_after
        self._expiration_trigger: CALLBACK_TYPE | None = None
        self._attr_name = name
        self._attr_unique_id = f"{receiver_entry_id}_{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{receiver_device}_{config[CONF_ID]}")},
            manufacturer="LaCrosse",
            model=f"Sensor ID {config[CONF_ID]}",
            name=sensor_device_name(config),
        )

        lacrosse.register_callback(
            int(self._config[CONF_ID]), self._callback_lacrosse, None
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel the expiration trigger when removed from Home Assistant."""
        if self._expiration_trigger:
            self._expiration_trigger()
            self._expiration_trigger = None
        await super().async_will_remove_from_hass()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "low_battery": self._low_battery,
            "new_battery": self._new_battery,
        }

    def _callback_lacrosse(
        self, lacrosse_sensor: pylacrosse.LaCrosseSensor, user_data: None
    ) -> None:
        """Handle a function that is called from pylacrosse with new values."""
        if self._expire_after is not None and self._expire_after > 0:
            # Reset old trigger
            if self._expiration_trigger:
                self._expiration_trigger()
                self._expiration_trigger = None

            # Set new trigger
            expiration_at = dt_util.utcnow() + timedelta(seconds=self._expire_after)

            self._expiration_trigger = async_track_point_in_utc_time(
                self.hass, self.value_is_expired, expiration_at
            )

        self._temperature = lacrosse_sensor.temperature
        self._humidity = lacrosse_sensor.humidity
        self._low_battery = lacrosse_sensor.low_battery
        self._new_battery = lacrosse_sensor.new_battery

    @callback
    def value_is_expired(self, *_: datetime) -> None:
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self.async_write_ha_state()


class LaCrosseTemperature(LaCrosseSensor):
    """Implementation of a Lacrosse temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._temperature


class LaCrosseHumidity(LaCrosseSensor):
    """Implementation of a Lacrosse humidity sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.HUMIDITY

    @property
    @override
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._humidity


class LaCrosseBattery(LaCrosseSensor):
    """Implementation of a Lacrosse battery sensor."""

    @property
    @override
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self._low_battery is None:
            return None
        if self._low_battery is True:
            return "low"
        return "ok"

    @property
    @override
    def icon(self) -> str:
        """Icon to use in the frontend."""
        if self._low_battery is None:
            return "mdi:battery-unknown"
        if self._low_battery is True:
            return "mdi:battery-alert"
        return "mdi:battery"


TYPE_CLASSES: dict[str, type[LaCrosseSensor]] = {
    "temperature": LaCrosseTemperature,
    "humidity": LaCrosseHumidity,
    "battery": LaCrosseBattery,
}
