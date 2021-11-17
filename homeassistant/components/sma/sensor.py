"""SMA Solar Webconnect interface."""
from __future__ import annotations

import logging
from typing import Any

import pysma
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.sma.entities import SENSOR_ENTITIES
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_CUSTOM,
    CONF_FACTOR,
    CONF_GROUP,
    CONF_KEY,
    CONF_UNIT,
    DOMAIN,
    GROUPS,
    PYSMA_COORDINATOR,
    PYSMA_DEVICE_INFO,
    PYSMA_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


def _check_sensor_schema(conf: dict[str, Any]) -> dict[str, Any]:
    """Check sensors and attributes are valid."""
    try:
        valid = [s.name for s in pysma.sensor.Sensors()]
        valid += pysma.const.LEGACY_MAP.keys()
    except (ImportError, AttributeError):
        return conf

    customs = list(conf[CONF_CUSTOM])

    for sensor in conf[CONF_SENSORS]:
        if sensor in customs:
            _LOGGER.warning(
                "All custom sensors will be added automatically, no need to include them in sensors: %s",
                sensor,
            )
        elif sensor not in valid:
            raise vol.Invalid(f"{sensor} does not exist")
    return conf


CUSTOM_SCHEMA = vol.Any(
    {
        vol.Required(CONF_KEY): vol.All(cv.string, vol.Length(min=13, max=15)),
        vol.Required(CONF_UNIT): cv.string,
        vol.Optional(CONF_FACTOR, default=1): vol.Coerce(float),
        vol.Optional(CONF_PATH): vol.All(cv.ensure_list, [cv.string]),
    }
)

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_SSL, default=False): cv.boolean,
            vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_GROUP, default=GROUPS[0]): vol.In(GROUPS),
            vol.Optional(CONF_SENSORS, default=[]): vol.Any(
                cv.schema_with_slug_keys(cv.ensure_list),  # will be deprecated
                vol.All(cv.ensure_list, [str]),
            ),
            vol.Optional(CONF_CUSTOM, default={}): cv.schema_with_slug_keys(
                CUSTOM_SCHEMA
            ),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    _check_sensor_schema,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Import the platform into a config entry."""
    _LOGGER.warning(
        "Loading SMA via platform setup is deprecated. "
        "Please remove it from your configuration"
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMA sensors."""
    sma_data = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = sma_data[PYSMA_COORDINATOR]
    used_sensors = sma_data[PYSMA_SENSORS]
    device_info = sma_data[PYSMA_DEVICE_INFO]

    entities = []
    for sensor in used_sensors:
        entities.append(
            SMAsensor(
                coordinator,
                config_entry.unique_id,
                device_info,
                next(
                    (e for e in SENSOR_ENTITIES if e.key == sensor.name),
                    SensorEntityDescription(key=sensor.name, name=sensor.name),
                ),
                sensor,
            )
        )

    async_add_entities(entities)


class SMAsensor(CoordinatorEntity, SensorEntity):
    """Representation of a SMA sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        config_entry_unique_id: str,
        description: SensorEntityDescription,
        device_info: DeviceInfo,
        pysma_sensor: pysma.sensor.Sensor,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor = pysma_sensor

        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{config_entry_unique_id}-{self._sensor.key}_{self._sensor.key_idx}"
        )

        # Set sensor enabled to False.
        # Will be enabled by async_added_to_hass if actually used.
        self._sensor.enabled = False

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._sensor.value

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._sensor.enabled = True

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self._sensor.enabled = False
