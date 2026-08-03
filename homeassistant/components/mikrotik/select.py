"""Support for Mikrotik routers select entities."""

from typing import Final, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MikrotikConfigEntry, mikrotik_config_entry_errors
from .entity import MikrotikDeviceEntity

PARALLEL_UPDATES = 0


SELECTS: Final = (
    SelectEntityDescription(
        key="poe-out",
        translation_key="poe_out",
        entity_category=EntityCategory.CONFIG,
        options=["off", "auto-on", "forced-on"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MikrotikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities based on a config entry."""
    coordinator = entry.runtime_data

    select_list = [
        MikrotikSelectEntity(entry, coordinator, switch_desc, interface)
        for switch_desc in SELECTS
        for interface in coordinator.api.interfaces
        if interface.get(switch_desc.key) is not None
    ]

    async_add_entities(select_list)


class MikrotikSelectEntity(MikrotikDeviceEntity, SelectEntity):
    """Representation of a select entity."""

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known option."""
        await super().async_added_to_hass()
        self._attr_current_option = self._interface.get("poe-out", "off")

    @override
    def _handle_coordinator_update(self) -> None:
        """Sync the selected option from the latest coordinator data."""
        self._attr_current_option = self._interface.get("poe-out", "off")
        super()._handle_coordinator_update()

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        with mikrotik_config_entry_errors():
            await self.hass.async_add_executor_job(
                self.coordinator.api.command,
                "/interface/ethernet/poe/set",
                {".id": self._interface[".id"], "poe-out": option},
            )

        await self.coordinator.async_request_refresh()
