"""Vistapool Switch entities."""

from dataclasses import dataclass
from typing import Any

from aioaquarite import AquariteError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN, PATH_HASHIDRO
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VistapoolSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Vistapool switch entity."""

    value_path: str
    extra_read_paths: tuple[str, ...] = ()
    exists_path: str | tuple[str, ...] | None = None
    translation_placeholders: dict[str, str] | None = None


SWITCH_DESCRIPTIONS: tuple[VistapoolSwitchEntityDescription, ...] = (
    VistapoolSwitchEntityDescription(
        key="filtration",
        translation_key="filtration",
        value_path="filtration.status",
    ),
    *(
        VistapoolSwitchEntityDescription(
            key=f"relay_{i}",
            translation_key="relay",
            translation_placeholders={"number": str(i)},
            value_path=f"relays.relay{i}.info.onoff",
            extra_read_paths=(f"relays.relay{i}.info.status",),
        )
        for i in (1, 2, 3, 4)
    ),
    VistapoolSwitchEntityDescription(
        key="electrolysis_cover",
        translation_key="electrolysis_cover",
        value_path="hidro.cover_enabled",
        exists_path=PATH_HASHIDRO,
    ),
    VistapoolSwitchEntityDescription(
        key="electrolysis_boost",
        translation_key="electrolysis_boost",
        value_path="hidro.cloration_enabled",
        exists_path=PATH_HASHIDRO,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool switches for every pool on the account."""
    entities: list[SwitchEntity] = []

    for coordinator in entry.runtime_data.coordinators.values():
        for description in SWITCH_DESCRIPTIONS:
            if description.exists_path is not None:
                required = (
                    (description.exists_path,)
                    if isinstance(description.exists_path, str)
                    else description.exists_path
                )
                if not all(coordinator.get_value(path) for path in required):
                    continue
            entities.append(VistapoolSwitch(coordinator, description))

        if coordinator.get_value("filtration.hasHeat"):
            entities.append(
                VistapoolSwitch(
                    coordinator,
                    VistapoolSwitchEntityDescription(
                        key="heating_climate",
                        translation_key="heating_climate",
                        value_path="filtration.heating.clima",
                    ),
                )
            )

        if coordinator.get_value("filtration.hasSmart"):
            entities.append(
                VistapoolSwitch(
                    coordinator,
                    VistapoolSwitchEntityDescription(
                        key="smart_mode_freeze",
                        translation_key="smart_mode_freeze",
                        value_path="filtration.smart.freeze",
                    ),
                )
            )

    async_add_entities(entities)


class VistapoolSwitch(VistapoolEntity, SwitchEntity):
    """Generic Vistapool switch driven by an entity description."""

    entity_description: VistapoolSwitchEntityDescription

    def __init__(
        self,
        coordinator: VistapoolDataUpdateCoordinator,
        description: VistapoolSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)
        if description.translation_placeholders is not None:
            self._attr_translation_placeholders = description.translation_placeholders

    @property
    def is_on(self) -> bool | None:
        """Return true if the writable path or any extra read path is truthy."""
        value = self.coordinator.get_value(self.entity_description.value_path)
        if value is None:
            return None
        on = value in (True, "1")
        for extra_path in self.entity_description.extra_read_paths:
            extra = self.coordinator.get_value(extra_path)
            if extra is not None:
                on = on or extra in (True, "1")
        return on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_value(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_value(0)

    async def _async_set_value(self, value: int) -> None:
        """Send a value update via the Vistapool cloud API."""
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id,
                self.entity_description.value_path,
                value,
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
