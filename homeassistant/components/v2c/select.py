"""Select platform for V2C settings."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from typing import Any

from pytrydan import Trydan, TrydanData
from pytrydan.models.trydan import ChargeMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import V2CConfigEntry, V2CUpdateCoordinator
from .entity import V2CBaseEntity


def charge_mode_value(value: ChargeMode) -> str:
    """Return the charge mode option value."""
    return value.name.lower()


@dataclass(frozen=True, kw_only=True)
class V2CSelectEntityDescription(SelectEntityDescription):
    """Describes V2C EVSE select entity."""

    current_option_fn: Callable[[TrydanData], str | None]
    options: list[str]
    update_fn: Callable[[Trydan, str], Coroutine[Any, Any, None]]


CHARGE_MODE_OPTIONS = [charge_mode_value(mode) for mode in ChargeMode]

TRYDAN_SELECTS = (
    V2CSelectEntityDescription(
        key="charge_mode",
        translation_key="charge_mode",
        entity_category=EntityCategory.CONFIG,
        options=CHARGE_MODE_OPTIONS,
        current_option_fn=lambda evse_data: (
            charge_mode_value(evse_data.charge_mode)
            if evse_data.charge_mode is not None
            else None
        ),
        update_fn=lambda evse, option: evse.charge_mode(ChargeMode[option.upper()]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up V2C Trydan select platform."""
    coordinator = config_entry.runtime_data
    data = coordinator.data
    assert data is not None

    async_add_entities(
        V2CSelectEntity(
            coordinator,
            replace(
                description,
                entity_registry_enabled_default=description.current_option_fn(data)
                is not None,
            ),
            config_entry.entry_id,
        )
        for description in TRYDAN_SELECTS
    )


class V2CSelectEntity(V2CBaseEntity, SelectEntity):
    """Representation of V2C EVSE settings select entity."""

    entity_description: V2CSelectEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CSelectEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C select entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.current_option_fn(self.data)

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return self.entity_description.options

    async def async_select_option(self, option: str) -> None:
        """Update the setting."""
        await self.entity_description.update_fn(self.coordinator.evse, option)
        await self.coordinator.async_request_refresh()
