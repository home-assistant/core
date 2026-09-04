"""Support for LaCrosse sensor components."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Final, override

import pylacrosse
import voluptuous as vol

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
    CONF_UNIQUE_ID,
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
    DEFAULT_DEVICE,
    DOMAIN,
    TYPES,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LaCrosseSensorDescription(SensorEntityDescription):
    """Class describing a LaCrosse sensor entity."""

    value_fn: Callable[[pylacrosse.LaCrosseSensor | None], float | int | str | None]


def _battery_value(sensor: pylacrosse.LaCrosseSensor | None) -> str | None:
    """Return the battery state."""
    if sensor is None or sensor.low_battery is None:
        return None
    if sensor.low_battery:
        return "low"
    return "ok"


SENSOR_TYPES: Final[dict[str, LaCrosseSensorDescription]] = {
    "temperature": LaCrosseSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.temperature if sensor else None,
    ),
    "humidity": LaCrosseSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.humidity if sensor else None,
    ),
    "battery": LaCrosseSensorDescription(
        key="battery",
        translation_key="battery",
        value_fn=_battery_value,
    ),
}


SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_TYPE): vol.In(TYPES),
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
        vol.Optional(CONF_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
        vol.Optional(CONF_BAUD, default=DEFAULT_BAUD): cv.positive_int,
        vol.Optional(CONF_DATARATE): cv.positive_int,
        vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
        vol.Optional(CONF_FREQUENCY): cv.positive_int,
        vol.Optional(CONF_JEELINK_LED): cv.boolean,
        vol.Optional(CONF_TOGGLE_INTERVAL): cv.positive_int,
        vol.Optional(CONF_TOGGLE_MASK): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaCrosseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaCrosse sensors from a config entry."""
    _add_sensors(hass, entry.runtime_data, dict(entry.data), async_add_entities)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the LaCrosse sensors."""
    hass.add_job(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


def _add_sensors(
    hass: HomeAssistant,
    lacrosse: pylacrosse.LaCrosse,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
) -> None:
    """Create entities for the configured LaCrosse sensors."""
    sensors: list[LaCrosseSensor] = []
    for device, device_config in config[CONF_SENSORS].items():
        _LOGGER.debug("%s %s", device, device_config)

        typ: str = device_config[CONF_TYPE]
        description = SENSOR_TYPES[typ]
        expire_after: int | None = device_config.get(CONF_EXPIRE_AFTER)

        sensors.append(
            LaCrosseSensor(
                hass,
                lacrosse,
                config[CONF_DEVICE],
                device,
                expire_after,
                device_config,
                description,
            )
        )

    add_entities(sensors)


def sensor_device_name(config: ConfigType) -> str:
    """Return the configured or default sensor device name."""
    if isinstance(friendly_name := config.get(CONF_FRIENDLY_NAME), str):
        return friendly_name
    return f"LaCrosse sensor {config[CONF_ID]}"


class LaCrosseSensor(SensorEntity):
    """Implementation of a Lacrosse sensor."""

    _attr_has_entity_name = True
    entity_description: LaCrosseSensorDescription
    _temperature: float | None = None
    _humidity: int | None = None
    _low_battery: bool | None = None
    _new_battery: bool | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        lacrosse: pylacrosse.LaCrosse,
        receiver_device: str,
        device_id: str,
        expire_after: int | None,
        config: ConfigType,
        description: LaCrosseSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._config = config
        self.entity_description = description
        self._expire_after = expire_after
        self._sensor_data: pylacrosse.LaCrosseSensor | None = None
        self._expiration_trigger: CALLBACK_TYPE | None = None
        self._attr_unique_id = config.get(CONF_UNIQUE_ID, device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{receiver_device}_{config[CONF_ID]}")},
            manufacturer="LaCrosse",
            model=f"Sensor ID {config[CONF_ID]}",
            name=sensor_device_name(config),
        )

        lacrosse.register_callback(
            int(self._config[CONF_ID]), self._callback_lacrosse, None
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "low_battery": self._low_battery,
            "new_battery": self._new_battery,
        }

    @property
    @override
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._sensor_data)

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
        self._sensor_data = lacrosse_sensor

    @callback
    def value_is_expired(self, *_: datetime) -> None:
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self.async_write_ha_state()

    @property
    @override
    def icon(self) -> str | None:
        """Icon to use in the frontend."""
        if self.entity_description.key != "battery":
            return None
        if self._sensor_data is None or self._sensor_data.low_battery is None:
            return "mdi:battery-unknown"
        if self._sensor_data.low_battery:
            return "mdi:battery-alert"
        return "mdi:battery"
