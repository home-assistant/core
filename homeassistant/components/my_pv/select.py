"""Creates Select entities for the my-PV Home Assistant integration."""

from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyPVConfigEntry
from .const import DOMAIN
from .entity import MyPVSetupEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV select."""
    coordinator = config_entry.runtime_data
    entities = []

    config = coordinator.device.get_setup_configuration("bstmode")
    if config and config.get("type") == "enumeration":
        entity_description = SelectEntityDescription(
            key="bstmode",
            entity_category=EntityCategory.CONFIG,
            translation_key="bstmode",
            entity_registry_enabled_default=False,
            options=list(config.get("options", {}).keys()),
        )
        entities.append(
            MyPVSelect(
                coordinator,
                entity_description,
                coordinator.device.serial_number,
            )
        )

    async_add_entities(entities)


class MyPVSelect(MyPVSetupEntity, SelectEntity):
    """my-PV select."""

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        value = self.coordinator.device.get_setup_value(self.entity_description.key)
        return str(value) if value is not None else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if not await self.coordinator.set_setup_value(
            self.entity_description.key, option
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )
