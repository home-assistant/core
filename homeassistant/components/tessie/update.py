"""Update platform for Tessie integration."""
from __future__ import annotations

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TessieUpdateStatus
from .coordinator import TessieDataUpdateCoordinator
from .entity import TessieEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie Update platform from a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(TessieUpdateEntity(coordinator) for coordinator in coordinators)


class TessieUpdateEntity(TessieEntity, UpdateEntity):
    """Tessie Updates entity."""

    _attr_supported_features = UpdateEntityFeature.PROGRESS
    _attr_name = None

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
    ) -> None:
        """Initialize the Update."""
        super().__init__(coordinator, "update")

    @property
    def installed_version(self) -> str:
        """Return the current app version."""
        # Discard build from version number
        return self.coordinator.data["vehicle_state_car_version"].split(" ")[0]

    @property
    def latest_version(self) -> str | None:
        """Return the latest version."""
        if self.get("vehicle_state_software_update_status") in (
            TessieUpdateStatus.AVAILABLE,
            TessieUpdateStatus.SCHEDULED,
            TessieUpdateStatus.INSTALLING,
            TessieUpdateStatus.DOWNLOADING,
            TessieUpdateStatus.WIFI_WAIT,
        ):
            return self.get("vehicle_state_software_update_version")
        return None

    @property
    def in_progress(self) -> bool | int | None:
        """Update installation progress."""
        if (
            self.get("vehicle_state_software_update_status")
            == TessieUpdateStatus.INSTALLING
        ):
            return self.get("vehicle_state_software_update_install_perc")
        return False
