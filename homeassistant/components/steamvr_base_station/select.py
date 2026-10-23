"""Power mode and channel selects for SteamVR Base Station."""

from typing import override

from lighthouse_ble import PowerState
from lighthouse_ble.const import CHANNEL_MAX, CHANNEL_MIN

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SteamVRBaseStationConfigEntry
from .entity import SteamVRBaseStationEntity

# Commands to one station are serialized by the library.
PARALLEL_UPDATES = 0

POWER_MODE = SelectEntityDescription(key="power_mode", translation_key="power_mode")
CHANNEL = SelectEntityDescription(
    key="channel",
    translation_key="channel",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    options=[str(channel) for channel in range(CHANNEL_MIN, CHANNEL_MAX + 1)],
)

MODE_FOR_STATE = {
    PowerState.ON: PowerState.ON,
    PowerState.BOOTING: PowerState.ON,
    PowerState.STANDBY: PowerState.STANDBY,
    PowerState.SLEEP: PowerState.SLEEP,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamVRBaseStationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the selects."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SteamVRBaseStationPowerModeSelect(coordinator, POWER_MODE),
            SteamVRBaseStationChannelSelect(coordinator, CHANNEL),
        ]
    )


class SteamVRBaseStationPowerModeSelect(SteamVRBaseStationEntity, SelectEntity):
    """Chooses between on, standby and sleep."""

    @property
    @override
    def options(self) -> list[str]:
        """Return the modes the station's firmware supports."""
        if self.coordinator.station.supports_standby is False:
            return [PowerState.ON, PowerState.SLEEP]
        return [PowerState.ON, PowerState.STANDBY, PowerState.SLEEP]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the mode the station is in or heading to."""
        if (power := self.coordinator.station.state.power) is None:
            return None
        return MODE_FOR_STATE.get(power)

    @override
    async def async_select_option(self, option: str) -> None:
        """Switch the station to the chosen mode."""
        await self.coordinator.async_set_power(PowerState(option))


class SteamVRBaseStationChannelSelect(SteamVRBaseStationEntity, SelectEntity):
    """The station's tracking channel."""

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current channel."""
        if (channel := self.coordinator.station.state.channel) is None:
            return None
        return str(channel)

    @override
    async def async_select_option(self, option: str) -> None:
        """Move the station to another channel."""
        await self.coordinator.async_set_channel(int(option))
