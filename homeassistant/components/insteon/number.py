"""Support for Insteon select entities."""

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_ADD_CONFIG_ENTITIES
from .insteon_entity import InsteonConfigEntity
from .utils import async_add_insteon_config_entities, async_add_insteon_devices_config


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Insteon covers from a config entry."""

    @callback
    def async_add_insteon_select_config_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_config_entities(
            hass,
            Platform.NUMBER,
            InsteonNumberConfigEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_CONFIG_ENTITIES}_{Platform.NUMBER}"
    async_dispatcher_connect(hass, signal, async_add_insteon_select_config_entities)
    async_add_insteon_devices_config(
        hass, Platform.NUMBER, InsteonNumberConfigEntity, async_add_entities
    )


class InsteonNumberConfigEntity(InsteonConfigEntity, NumberEntity):
    """A class for an Insteon config select Enum entity."""

    _attr_native_min_value: float = 0
    _attr_native_max_value: float = 65535
    _attr_native_step: float = 0.1

    def __init__(self, device, name) -> None:
        """Init the InsteonNumberConfigEntity class."""
        super().__init__(device=device, group=None, name=name)
        self._attr_name = self._entity.name
        self._debouncer: Debouncer

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self._entity.value

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value from HA."""
        self._entity.new_value = value
        await self._debounce_writer.async_call()
