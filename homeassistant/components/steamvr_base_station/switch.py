"""Power switch for SteamVR Base Station."""

from typing import Any, override

from lighthouse_ble import PowerState

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SteamVRBaseStationConfigEntry
from .entity import SteamVRBaseStationEntity

# Commands to one station are serialized by the library.
PARALLEL_UPDATES = 0

POWER = SwitchEntityDescription(key="power", name=None)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamVRBaseStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the power switch."""
    async_add_entities([SteamVRBaseStationSwitch(entry.runtime_data, POWER)])


class SteamVRBaseStationSwitch(SteamVRBaseStationEntity, SwitchEntity):
    """Wakes the station or puts it to sleep."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True while the station is on or on its way there."""
        power = self.coordinator.station.state.power
        if power is None or power is PowerState.UNKNOWN:
            return None
        return power in (PowerState.ON, PowerState.BOOTING)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the station."""
        await self.coordinator.async_set_power(PowerState.ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Put the station to sleep."""
        await self.coordinator.async_set_power(PowerState.SLEEP)
