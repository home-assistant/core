"""The select entities for musiccast."""

from aiomusiccast.configurables import OptionSetter

from homeassistant.components.select import SelectEntity
from homeassistant.components.yamaha_musiccast import (
    DOMAIN,
    MusicCastDataUpdateCoordinator,
    MusicCastDeviceEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    select_entities = []

    for configurable in coordinator.data.configurables:
        if isinstance(configurable, OptionSetter):
            select_entities.append(ConfigurableOption(coordinator, configurable))

    for zone, data in coordinator.data.zones.items():
        for configurable in data.configurables:
            if isinstance(configurable, OptionSetter):
                select_entities.append(
                    ConfigurableOption(coordinator, configurable, zone)
                )

    async_add_entities(select_entities)


class ConfigurableOption(MusicCastDeviceEntity, SelectEntity):
    """Representation of a MusicCast Alarm entity."""

    def __init__(
        self,
        coordinator: MusicCastDataUpdateCoordinator,
        configurable: OptionSetter,
        zone_id: str = None,
    ) -> None:
        """Initialize the switch."""
        if zone_id is not None:
            self._zone_id = zone_id
        self.configurable = configurable
        super().__init__(name=configurable.name, icon="", coordinator=coordinator)

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        # Sensors should also register callbacks to HA when their state changes
        self.coordinator.musiccast.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        await super().async_added_to_hass()
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this media_player."""
        return f"{self.device_id}_{self.configurable.id}"

    async def async_select_option(self, option: str) -> None:
        """Select the given option."""
        await self.configurable.set(option)

    @property
    def options(self):
        """Return the list possible options."""
        return list(self.configurable.options.keys())

    def current_option(self):
        """Return the currently selected option."""
        return self.configurable.current
