"""Switch platform for Qube Heat Pump."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import QubeConfigEntry
from .const import DOMAIN
from .coordinator import QubeCoordinator
from .entity import QubeEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class QubeSwitchEntityDescription(SwitchEntityDescription):
    """Switch entity description for Qube Heat Pump."""

    register_key: str


SWITCH_TYPES: tuple[QubeSwitchEntityDescription, ...] = (
    QubeSwitchEntityDescription(
        key="summer_mode",
        translation_key="summer_mode",
        register_key="bms_summerwinter",
    ),
    QubeSwitchEntityDescription(
        key="anti_legionella_cycle",
        translation_key="anti_legionella_cycle",
        register_key="antilegionella_frcstart_ant",
    ),
    QubeSwitchEntityDescription(
        key="heating_curve",
        translation_key="heating_curve",
        entity_category=EntityCategory.CONFIG,
        register_key="en_plantsetp_compens",
    ),
    QubeSwitchEntityDescription(
        key="heating_demand",
        translation_key="heating_demand",
        register_key="modbus_demand",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QubeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Qube switches."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        QubeSwitch(coordinator, entry, description) for description in SWITCH_TYPES
    )


class QubeSwitch(QubeEntity, SwitchEntity):
    """Qube switch entity."""

    entity_description: QubeSwitchEntityDescription

    def __init__(
        self,
        coordinator: QubeCoordinator,
        entry: QubeConfigEntry,
        description: QubeSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.entity_description.register_key in self.coordinator.data.switches
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self.coordinator.data.switches.get(self.entity_description.register_key)

    async def _async_write_switch(self, value: bool) -> None:
        """Write switch value to the device."""
        register_key = self.entity_description.register_key
        try:
            success = await self.coordinator.client.write_switch(register_key, value)
        except (ConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_command_failed",
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_write_switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_write_switch(False)
