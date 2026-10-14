"""Plugwise Switch component for HomeAssistant."""

from dataclasses import dataclass
from typing import Any, override

from plugwise.constants import SwitchType

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PlugwiseConfigEntry, PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import deprecate_entity, plugwise_command

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class PlugwiseSwitchEntityDescription(SwitchEntityDescription):
    """Describes Plugwise switch entity."""

    key: SwitchType


SWITCHES: tuple[PlugwiseSwitchEntityDescription, ...] = (
    PlugwiseSwitchEntityDescription(
        key="dhw_cm_switch",
        translation_key="dhw_cm_switch",
        entity_category=EntityCategory.CONFIG,
    ),
    PlugwiseSwitchEntityDescription(
        key="lock",
        translation_key="lock",
        entity_category=EntityCategory.CONFIG,
    ),
    PlugwiseSwitchEntityDescription(
        key="relay",
        translation_key="relay",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    PlugwiseSwitchEntityDescription(
        key="cooling_ena_switch",
        translation_key="cooling_ena_switch",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smile switches from a config entry."""
    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        entities: list[SwitchEntity] = []
        for device_id in coordinator.new_devices:
            if not (switches := coordinator.data[device_id].get("switches")):
                continue
            for description in SWITCHES:
                if description.key not in switches:
                    continue
                if description.key == "dhw_cm_switch":
                    if not deprecate_entity(
                        hass,
                        entity_registry,
                        async_on_unload=entry.async_on_unload,
                        platform_domain=Platform.SWITCH,
                        entity_unique_id=f"{device_id}-dhw_cm_switch",
                        issue_id=f"deprecated_dhw_cm_switch_{device_id}",
                        translation_key="deprecated_dhw_cm_switch",
                    ):
                        continue
                    entities.append(
                        PlugwiseDhwCmSwitchEntity(coordinator, device_id, description)
                    )
                else:
                    entities.append(
                        PlugwiseSwitchEntity(coordinator, device_id, description)
                    )

        async_add_entities(entities)

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseSwitchEntity(PlugwiseEntity, SwitchEntity):
    """Representation of a Plugwise plug."""

    entity_description: PlugwiseSwitchEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: PlugwiseSwitchEntityDescription,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}-{description.key}"
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.device["switches"][self.entity_description.key]

    @plugwise_command
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.coordinator.api.set_switch_state(
            self._dev_id,
            self.device.get("members"),
            self.entity_description.key,
            "on",
        )

    @plugwise_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.coordinator.api.set_switch_state(
            self._dev_id,
            self.device.get("members"),
            self.entity_description.key,
            "off",
        )


class PlugwiseDhwCmSwitchEntity(PlugwiseSwitchEntity):
    """Represent the deprecated DHW comfort switch."""

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the deprecated DHW comfort switch on."""
        await super().async_turn_on(**kwargs)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the deprecated DHW comfort switch off."""
        await super().async_turn_off(**kwargs)
