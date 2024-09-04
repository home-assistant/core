"""Interfaces with TotalConnect buttons."""

from collections.abc import Callable
from dataclasses import dataclass

from total_connect_client.location import TotalConnectLocation
from total_connect_client.zone import TotalConnectZone

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TotalConnectDataUpdateCoordinator
from .entity import TotalConnectLocationEntity, TotalConnectZoneEntity


@dataclass(frozen=True, kw_only=True)
class TotalConnectButtonEntityDescription(ButtonEntityDescription):
    """TotalConnect button description."""

    press_fn: Callable[[TotalConnectLocation], None]


PANEL_BUTTONS: tuple[TotalConnectButtonEntityDescription, ...] = (
    TotalConnectButtonEntityDescription(
        key="clear_bypass",
        translation_key="clear_bypass",
        press_fn=lambda location: location.clear_bypass(),
    ),
    TotalConnectButtonEntityDescription(
        key="bypass_all",
        translation_key="bypass_all",
        press_fn=lambda location: location.zone_bypass_all(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect buttons based on a config entry."""
    buttons: list = []
    coordinator: TotalConnectDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for location_id, location in coordinator.client.locations.items():
        buttons.extend(
            TotalConnectPanelButton(coordinator, location, description)
            for description in PANEL_BUTTONS
        )

        buttons.extend(
            TotalConnectZoneBypassButton(coordinator, zone, location_id)
            for zone in location.zones.values()
            if zone.can_be_bypassed
        )

    async_add_entities(buttons)


class TotalConnectZoneBypassButton(TotalConnectZoneEntity, ButtonEntity):
    """Represent a TotalConnect zone bypass button."""

    _attr_translation_key = "bypass"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        zone: TotalConnectZone,
        location_id: str,
    ) -> None:
        """Initialize the TotalConnect status."""
        super().__init__(coordinator, zone, location_id, "bypass")

    def press(self) -> None:
        """Press the bypass button."""
        self._zone.bypass()


class TotalConnectPanelButton(TotalConnectLocationEntity, ButtonEntity):
    """Generic TotalConnect panel button."""

    entity_description: TotalConnectButtonEntityDescription

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        location: TotalConnectLocation,
        entity_description: TotalConnectButtonEntityDescription,
    ) -> None:
        """Initialize the TotalConnect button."""
        super().__init__(coordinator, location)
        self.entity_description = entity_description
        self._attr_unique_id = f"{location.location_id}_{entity_description.key}"

    def press(self) -> None:
        """Press the button."""
        self.entity_description.press_fn(self._location)
