"""Support for WLED button."""

from typing import override

from awesomeversion import AwesomeVersion

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import WLEDConfigEntry, WLEDDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import wled_exception_handler

PARALLEL_UPDATES = 1

# WLED skips to the next playlist entry on request since 0.15.0. Forks like
# WLED-MM number their releases 14 and up, which also sorts after it.
NEXT_PLAYLIST_ENTRY_MIN_VERSION = AwesomeVersion("0.15.0")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up WLED button based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([WLEDRestartButton(coordinator)])

    # Firmware that can skip a playlist entry can be installed later, like
    # with the update entity, so keep an eye out for it.
    next_playlist_entry_added = False

    @callback
    def async_add_next_playlist_entry_button() -> None:
        """Add the next playlist entry button once the firmware supports it."""
        nonlocal next_playlist_entry_added
        if next_playlist_entry_added or (
            (version := coordinator.data.info.version) is None
            or version < NEXT_PLAYLIST_ENTRY_MIN_VERSION
        ):
            return

        next_playlist_entry_added = True
        async_add_entities([WLEDNextPlaylistEntryButton(coordinator)])

    entry.async_on_unload(
        coordinator.async_add_listener(async_add_next_playlist_entry_button)
    )
    async_add_next_playlist_entry_button()


class WLEDRestartButton(WLEDEntity, ButtonEntity):
    """Defines a WLED restart button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_restart"

    @wled_exception_handler
    @override
    async def async_press(self) -> None:
        """Send out a restart command."""
        await self.coordinator.wled.reset()


class WLEDNextPlaylistEntryButton(WLEDEntity, ButtonEntity):
    """Defines a WLED button to skip to the next playlist entry."""

    _attr_translation_key = "next_playlist_entry"

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = (
            f"{coordinator.data.info.mac_address}_next_playlist_entry"
        )

    @wled_exception_handler
    @override
    async def async_press(self) -> None:
        """Skip to the next entry of the running playlist."""
        # The device ignores the request without a playlist; say why instead.
        if self.coordinator.data.state.playlist_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_playlist_running",
            )

        await self.coordinator.wled.next_playlist_entry()
