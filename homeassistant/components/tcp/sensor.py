"""Support for TCP socket based sensors."""

from typing import Final, override

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import TcpConfigEntry
from .common import TCP_PLATFORM_SCHEMA, async_import_yaml
from .entity import TcpEntity

PLATFORM_SCHEMA: Final = SENSOR_PLATFORM_SCHEMA.extend(TCP_PLATFORM_SCHEMA)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML configuration."""
    await async_import_yaml(hass, config, Platform.SENSOR)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TcpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TCP sensor."""
    entity = await hass.async_add_executor_job(TcpSensor, hass, entry)
    async_add_entities(
        [entity],
        update_before_add=True,
    )


class TcpSensor(TcpEntity, SensorEntity):
    """Implementation of a TCP socket based sensor."""

    _entity_id_format = ENTITY_ID_FORMAT

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self._state

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        return self._config[CONF_UNIT_OF_MEASUREMENT]
