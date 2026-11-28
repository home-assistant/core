"""Provides a binary sensor which gets its values from a TCP socket."""

from typing import Final, override

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TcpConfigEntry
from .common import TCP_PLATFORM_SCHEMA, async_import_yaml
from .const import CONF_VALUE_ON
from .entity import TcpEntity

PLATFORM_SCHEMA: Final = BINARY_SENSOR_PLATFORM_SCHEMA.extend(TCP_PLATFORM_SCHEMA)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML configuration."""
    await async_import_yaml(hass, config, Platform.BINARY_SENSOR)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TcpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TCP binary sensor."""
    entity = await hass.async_add_executor_job(TcpBinarySensor, hass, entry)
    async_add_entities([entity], update_before_add=True)


class TcpBinarySensor(TcpEntity, BinarySensorEntity):
    """A binary sensor which is on when its state == CONF_VALUE_ON."""

    _entity_id_format = ENTITY_ID_FORMAT

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state == self._config[CONF_VALUE_ON]
