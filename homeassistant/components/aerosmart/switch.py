"""Switch platform for aerosmart (writable boost functions).

Every entity here is disabled by default: writability was inferred from the
source register's name, not a manufacturer specification, and must be
verified against the real unit before being relied on.
"""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AerosmartConfigEntry
from .entity import AerosmartEntity

# Coordinator-based (all entities share one poll); parallel per-entity
# writes to the same Modbus link would race, so keep this serialized.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AerosmartSwitchEntityDescription(SwitchEntityDescription):
    """Describes an aerosmart switch entity."""

    component: str
    attribute: str


SWITCH_DESCRIPTIONS: tuple[AerosmartSwitchEntityDescription, ...] = (
    AerosmartSwitchEntityDescription(
        key="boost_functions_ventilation_function_heizung_plus",
        translation_key="boost_functions_ventilation_function_heizung_plus",
        component="boost_functions_ventilation",
        attribute="function_heizung_plus",
        entity_registry_enabled_default=False,
    ),
    AerosmartSwitchEntityDescription(
        key="boost_functions_heat_pump_function_bad_plus",
        translation_key="boost_functions_heat_pump_function_bad_plus",
        component="boost_functions_heat_pump",
        attribute="function_bad_plus",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AerosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up aerosmart switches."""
    runtime = entry.runtime_data
    async_add_entities(
        AerosmartSwitch(runtime.coordinator_for(description.component), description)
        for description in SWITCH_DESCRIPTIONS
    )


class AerosmartSwitch(AerosmartEntity, SwitchEntity):
    """A writable aerosmart boost-function toggle."""

    entity_description: AerosmartSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the register's value is non-zero."""
        value = getattr(self._subsystem, self.entity_description.attribute)
        return None if value is None else bool(value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the function on."""
        await self._subsystem.write(self.entity_description.attribute, 1)
        await self.coordinator.async_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the function off."""
        await self._subsystem.write(self.entity_description.attribute, 0)
        await self.coordinator.async_refresh()
