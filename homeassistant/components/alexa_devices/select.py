"""Support for select entities."""

from typing import Final

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import AmazonConfigEntry
from .entity import AmazonServiceEntity

PARALLEL_UPDATES = 1

SELECTS: Final = (
    SelectEntityDescription(
        key="default_device",
        translation_key="default_device",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        AmazonSelect(coordinator, select_desc) for select_desc in SELECTS
    )


class AmazonSelect(AmazonServiceEntity, SelectEntity, RestoreEntity):
    """Representation of a select entity for the default Alexa device."""

    @property
    def options(self) -> list[str]:
        """Return a list of available options."""
        return [device.account_name for device in self.coordinator.data.values()]

    async def async_added_to_hass(self) -> None:
        """Restore last known option."""
        await super().async_added_to_hass()
        if (default := self.coordinator.api.default_device) is not None:
            self._attr_current_option = default.account_name
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state in self.options:
            await self.async_select_option(last_state.state)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for device in self.coordinator.data.values():
            if device.account_name == option:
                self.coordinator.api.default_device = device
                self._attr_current_option = option
                self.async_write_ha_state()
                return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="select_option_not_found",
            translation_placeholders={"name": option},
        )
