"""Support for Mikrotik routers select entities."""

from typing import Final, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MikrotikConfigEntry, mikrotik_config_entry_errors
from .entity import MikrotikDeviceEntity

PARALLEL_UPDATES = 0

OPTION_TO_KEY: Final = {
    "off": "off",
    "auto_on": "auto-on",
    "forced_on": "forced-on",
}
KEY_TO_OPTION: Final = {value: key for key, value in OPTION_TO_KEY.items()}

SELECTS: Final = (
    SelectEntityDescription(
        key="poe-out",
        translation_key="poe_out",
        entity_category=EntityCategory.CONFIG,
        options=list(OPTION_TO_KEY.keys()),
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
        MikrotikSelectEntity(entry, coordinator, select_desc, interface)
        for select_desc in SELECTS
        for interface in coordinator.api.interfaces
        if interface.get(select_desc.key) is not None
    ]

    async_add_entities(select_list)


class MikrotikSelectEntity(MikrotikDeviceEntity, SelectEntity):
    """Representation of a select entity."""

    @property
    @override
    def current_option(self) -> str | None:
        """Return the state of the select."""
        if (value := self._interface.get(self.entity_description.key)) is None:
            return None
        return KEY_TO_OPTION[value]

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""

        with mikrotik_config_entry_errors():
            await self.hass.async_add_executor_job(
                self.coordinator.api.command,
                "/interface/ethernet/poe/set",
                {
                    ".id": self._interface[".id"],
                    self.entity_description.key: OPTION_TO_KEY[option],
                },
            )

        await self.coordinator.async_request_refresh()
