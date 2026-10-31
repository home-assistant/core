"""Select platform for the Vitesy integration."""

from typing import override

from aiovitesy.exceptions import VitesyError

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import VitesyConfigEntry, VitesyDataUpdateCoordinator, supports_mode
from .entity import VitesyEntity

PARALLEL_UPDATES = 1

# Raw AWS IoT shadow values for Shelfy, not program catalogue ids.


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitesyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitesy selects from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        VitesyModeSelect(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if supports_mode(device)
    )


class VitesyModeSelect(VitesyEntity, SelectEntity):
    """Select for the operating mode of a Vitesy device."""

    _attr_translation_key = "mode"
    _attr_options = ["eco", "shelf", "boost"]

    def __init__(
        self, coordinator: VitesyDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_mode"

    @property
    @override
    def available(self) -> bool:
        """Return True when the device's mode could be read."""
        return super().available and self._device_id in self.coordinator.mode_status

    @property
    @override
    def current_option(self) -> str | None:
        """Return the requested mode, which a sleeping device applies on wake."""
        status = self.coordinator.mode_status[self._device_id]
        return status.desired_mode or status.current_mode

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the device's operating mode."""
        try:
            await self.coordinator.api.set_mode(self._device_id, option)
        except VitesyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_mode_failed",
            ) from err
        await self.coordinator.async_request_refresh()
