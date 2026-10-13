"""Select platform for aerosmart (writable enum-coded registers).

Every entity here is disabled by default: writability and option codes were
confirmed against the official manufacturer documentation, but should still
be verified against the real unit before being relied on for anything
automated.
"""

from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AerosmartConfigEntry, AerosmartCoordinator
from .entity import AerosmartEntity

# Coordinator-based (all entities share one poll); parallel per-entity
# writes to the same Modbus link would race, so keep this serialized.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AerosmartSelectEntityDescription(SelectEntityDescription):
    """Describes an aerosmart select entity."""

    component: str
    attribute: str


SELECT_DESCRIPTIONS: tuple[AerosmartSelectEntityDescription, ...] = (
    AerosmartSelectEntityDescription(
        key="ventilation_betriebsart",
        translation_key="ventilation_betriebsart",
        component="ventilation",
        attribute="betriebsart",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AerosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up aerosmart selects."""
    runtime = entry.runtime_data
    async_add_entities(
        AerosmartSelect(runtime.coordinator_for(description.component), description)
        for description in SELECT_DESCRIPTIONS
    )


class AerosmartSelect(AerosmartEntity, SelectEntity):
    """A writable aerosmart enum-coded register."""

    entity_description: AerosmartSelectEntityDescription

    def __init__(
        self,
        coordinator: AerosmartCoordinator,
        entity_description: AerosmartSelectEntityDescription,
    ) -> None:
        """Initialize, deriving the option list from the field's enum metadata."""
        super().__init__(coordinator, entity_description)
        meta = self._subsystem.require_metadata_for(entity_description.attribute)
        assert meta.enum is not None
        self._code_to_label = dict(meta.enum.options)
        self._label_to_code = {label: code for code, label in meta.enum.options}
        self._attr_options = list(self._label_to_code)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the register's current value as its documented label."""
        value = getattr(self._subsystem, self.entity_description.attribute)
        return None if value is None else self._code_to_label.get(int(value))

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option's underlying enum code."""
        code = self._label_to_code[option]
        await self._subsystem.write(self.entity_description.attribute, code)
        await self.coordinator.async_refresh()
