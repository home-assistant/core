"""Support for Rain Bird Irrigation system LNK Wi-Fi Module."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_DURATION, CONF_IMPORTED_NAMES, CONF_ZONE_TYPE, ZONE_TYPE_VALVE
from .entity import RainBirdZoneEntity
from .types import RainbirdConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird irrigation switches."""
    if config_entry.options.get(CONF_ZONE_TYPE) == ZONE_TYPE_VALVE:
        return
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(
        RainBirdSwitch(
            coordinator,
            zone,
            config_entry.options[ATTR_DURATION],
            config_entry.data.get(CONF_IMPORTED_NAMES, {}).get(str(zone)),
        )
        for zone in coordinator.data.zones
    )


class RainBirdSwitch(RainBirdZoneEntity, SwitchEntity):
    """Representation of a Rain Bird switch."""

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_irrigate(**kwargs)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_stop_irrigation()

    @property
    @override
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._zone in self.coordinator.data.active_zones
