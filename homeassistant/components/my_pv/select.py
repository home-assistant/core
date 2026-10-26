"""Creates Select entities for the my-PV integration."""

from typing import Any, Final, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MyPVConfigEntry, MyPVCoordinator
from .entity import MyPVSetupEntity

PARALLEL_UPDATES = 0

ENTITY_DESCRIPTIONS: Final[tuple[SelectEntityDescription, ...]] = (
    SelectEntityDescription(
        key="bstmode",
        entity_category=EntityCategory.CONFIG,
        translation_key="bstmode",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV select."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MyPVSelect(coordinator, entity_description, config)
        for entity_description in ENTITY_DESCRIPTIONS
        if (
            config := coordinator.device.get_setup_configuration(entity_description.key)
        )
        and config.get("type") == "enumeration"
    )


class MyPVSelect(MyPVSetupEntity, SelectEntity):
    """my-PV select."""

    entity_description: SelectEntityDescription

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: SelectEntityDescription,
        config: dict[str, Any],
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, entity_description)

        self._attr_options = list(config.get("options", {}).keys())

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
