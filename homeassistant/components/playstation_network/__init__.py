"""The PlayStation Network integration."""

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import CONF_NPSSO, DOMAIN
from .coordinator import (
    PlaystationNetworkConfigEntry,
    PlaystationNetworkFriendDataCoordinator,
    PlaystationNetworkFriendlistCoordinator,
    PlaystationNetworkGroupsUpdateCoordinator,
    PlaystationNetworkRuntimeData,
    PlaystationNetworkTrophyTitlesCoordinator,
    PlaystationNetworkUserDataCoordinator,
)
from .helpers import PlaystationNetwork

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Set up Playstation Network from a config entry."""

    psn = PlaystationNetwork(hass, entry.data[CONF_NPSSO])

    coordinator = PlaystationNetworkUserDataCoordinator(hass, psn, entry)
    await coordinator.async_config_entry_first_refresh()

    trophy_titles = PlaystationNetworkTrophyTitlesCoordinator(hass, psn, entry)

    groups = PlaystationNetworkGroupsUpdateCoordinator(hass, psn, entry)
    await groups.async_config_entry_first_refresh()

    friends_list = PlaystationNetworkFriendlistCoordinator(hass, psn, entry)

    friends = {}

    for subentry_id, subentry in entry.subentries.items():
        friend_coordinator = PlaystationNetworkFriendDataCoordinator(
            hass, psn, entry, subentry
        )
        await friend_coordinator.async_config_entry_first_refresh()
        friends[subentry_id] = friend_coordinator

    entry.runtime_data = PlaystationNetworkRuntimeData(
        coordinator, trophy_titles, groups, friends, friends_list
    )

    # Register the account device up front so entities on concurrently set up
    # platforms (media players, friends) can resolve it as their via_device.
    if TYPE_CHECKING:
        assert entry.unique_id
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        name=coordinator.data.username,
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Sony Interactive Entertainment",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
