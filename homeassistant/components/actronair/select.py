"""Support for Selecting an ACSystem to be controlled."""

from actronair_api import ACSystem

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

# from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AC_SYSTEMS_COORDINATOR,
    DOMAIN,
    NEO_WC,
    SELECTED_AC_SERIAL,
    SYSTEM_STATUS_COORDINATOR,
)
from .coordinator import (
    ActronAirACSystemsDataCoordinator,
    ActronAirSystemStatusDataCoordinator,
)
from .utility import get_serial_from_option_text

STORAGE_KEY = f"{DOMAIN}_selected_ac"
STORAGE_VERSION = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AC System selector."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    acSystemsCoordinator: ActronAirACSystemsDataCoordinator = coordinators[
        AC_SYSTEMS_COORDINATOR
    ]
    acSystemStatusCoordinator: ActronAirSystemStatusDataCoordinator = coordinators[
        SYSTEM_STATUS_COORDINATOR
    ]
    # Ensure the store exists
    store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load()
    selected_ac = stored_data.get(SELECTED_AC_SERIAL) if stored_data else None
    if selected_ac is not None:
        hass.data[DOMAIN][SELECTED_AC_SERIAL] = selected_ac

    # Add the AC selector entity
    async_add_entities(
        [
            ACSystemSelectEntity(
                hass,
                acSystemsCoordinator,
                acSystemStatusCoordinator,
                store,
                selected_ac,
            )
        ],
        update_before_add=True,
    )


class ACSystemSelectEntity(CoordinatorEntity, SelectEntity):
    """Select entity for choosing an AC system."""

    def getSystemDisplayName(self, ac: ACSystem) -> str:
        """Get the display name of the AC system."""
        displayName: str = ac.description + " (" + ac.serial + ")"
        return "" if displayName is None else displayName

    selected_ac: str = ""

    def __init__(
        self,
        hass: HomeAssistant,
        acSystemsCoordinator: ActronAirACSystemsDataCoordinator,
        acSystemStatusCoordinator: ActronAirSystemStatusDataCoordinator,
        store,
        selected_ac,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(acSystemStatusCoordinator)
        self.hass = hass
        self.store = store
        self.selected_ac = selected_ac

        # Get available AC systems
        self._attr_options = []
        self._attr_current_option = None

        if acSystemsCoordinator.acSystems is not None:
            for ac in list[ACSystem](acSystemsCoordinator.acSystems):
                if ac.type == NEO_WC:
                    displayName = self.getSystemDisplayName(ac)
                    self._attr_options.append(displayName)
                    if ac.serial == selected_ac:
                        self._attr_current_option = displayName

        if self._attr_current_option is None:
            if self._attr_options:
                self._attr_current_option = self._attr_options[0]
                serial = get_serial_from_option_text(self._attr_current_option)
                hass.data[DOMAIN][SELECTED_AC_SERIAL] = serial
                self.store.async_save({SELECTED_AC_SERIAL: serial})

        # Unique ID for the entity (so it persists in HA)
        self._attr_unique_id = f"{DOMAIN}_ac_system_selector"

        # Categorize as a CONFIG entity (appears in HA settings)
        self._attr_entity_category = EntityCategory.CONFIG

        # Name displayed in Home Assistant
        self._attr_name = "AC System Selector"

    async def async_added_to_hass(self) -> None:
        """Event - Entity is added to Home Assistant."""
        await super().async_added_to_hass()
        await self.store.async_save({SELECTED_AC_SERIAL: self.selected_ac})
        await self.coordinator.async_request_refresh()
        self._attr_available = True
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Handle selecting an AC system and persist it."""
        if option not in self._attr_options:
            raise ValueError(f"Invalid AC system: {option}")
        selected_ac_serial = get_serial_from_option_text(option)
        await self.store.async_save({SELECTED_AC_SERIAL: selected_ac_serial})
        self._attr_current_option = option
        self.hass.data[DOMAIN][SELECTED_AC_SERIAL] = selected_ac_serial
        self.async_write_ha_state()
        # Refresh data coordinator to fetch details for the new selection
        await self.coordinator.async_request_refresh()
