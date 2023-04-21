"""Support for Insteon select entities."""

from pyinsteon.config import RAMP_RATE_IN_SEC
from pyinsteon.constants import RAMP_RATES_SEC

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
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
            Platform.SELECT,
            InsteonSelectConfigEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_CONFIG_ENTITIES}_{Platform.SELECT}"
    async_dispatcher_connect(hass, signal, async_add_insteon_select_config_entities)
    async_add_insteon_devices_config(
        hass, Platform.SELECT, InsteonSelectConfigEntity, async_add_entities
    )


class InsteonSelectConfigEntity(InsteonConfigEntity, SelectEntity):
    """A class for an Insteon config select Enum entity."""

    def __init__(self, device, name) -> None:
        """Init the InsteonSelectConfigEntity class."""
        super().__init__(device=device, group=None, name=name)
        if self._entity.name == RAMP_RATE_IN_SEC:
            self._attribute = "ramp_rate"
            self._attr_options = [str(seconds) for seconds in RAMP_RATES_SEC]
        else:
            self._attribute = self._entity.value_type.__name__
            self._attr_options = [str(entry) for entry in self._entity.value_type]

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return str(self._entity.value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        option_value = self._entity.value_type[option.upper()]
        self._entity.new_value = option_value
        await self._debounce_writer.async_call()
