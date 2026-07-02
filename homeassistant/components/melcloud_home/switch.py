"""Switch platform for MELCloud Home."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from aiomelcloudhome import ATAUnit, ATWUnit, MELCloudHome
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ATASwitchEntityDescription(SwitchEntityDescription):
    """Class to hold MELCloud Home ATA switch description."""

    available_fn: Callable[[ATAUnit], bool]
    is_on_fn: Callable[[ATAUnit], bool | None]
    turn_on_fn: Callable[[MELCloudHome, ATAUnit], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[MELCloudHome, ATAUnit], Coroutine[Any, Any, None]]


@dataclass(frozen=True, kw_only=True)
class ATWSwitchEntityDescription(SwitchEntityDescription):
    """Class to hold MELCloud Home ATW switch description."""

    available_fn: Callable[[ATWUnit], bool]
    is_on_fn: Callable[[ATWUnit], bool | None]
    turn_on_fn: Callable[[MELCloudHome, ATWUnit], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[MELCloudHome, ATWUnit], Coroutine[Any, Any, None]]


ATA_SWITCHES: tuple[ATASwitchEntityDescription, ...] = (
    ATASwitchEntityDescription(
        key="frost_protection",
        translation_key="frost_protection",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        available_fn=lambda unit: unit.frost_protection is not None,
        is_on_fn=lambda unit: (
            unit.frost_protection.enabled if unit.frost_protection else None
        ),
        turn_on_fn=lambda client, unit: client.set_frost_protection(
            enabled=True,
            min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
            max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
            ata_unit_ids=[unit.id],
        ),
        turn_off_fn=lambda client, unit: client.set_frost_protection(
            enabled=False,
            min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
            max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
            ata_unit_ids=[unit.id],
        ),
    ),
    ATASwitchEntityDescription(
        key="overheat_protection",
        translation_key="overheat_protection",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        available_fn=lambda unit: unit.overheat_protection is not None,
        is_on_fn=lambda unit: (
            unit.overheat_protection.enabled if unit.overheat_protection else None
        ),
        turn_on_fn=lambda client, unit: client.set_overheat_protection(
            enabled=True,
            min_temp=unit.overheat_protection.min if unit.overheat_protection else 0.0,
            max_temp=unit.overheat_protection.max if unit.overheat_protection else 0.0,
            ata_unit_ids=[unit.id],
        ),
        turn_off_fn=lambda client, unit: client.set_overheat_protection(
            enabled=False,
            min_temp=unit.overheat_protection.min if unit.overheat_protection else 0.0,
            max_temp=unit.overheat_protection.max if unit.overheat_protection else 0.0,
            ata_unit_ids=[unit.id],
        ),
    ),
)

ATW_SWITCHES: tuple[ATWSwitchEntityDescription, ...] = (
    ATWSwitchEntityDescription(
        key="frost_protection",
        translation_key="frost_protection",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        available_fn=lambda unit: unit.frost_protection is not None,
        is_on_fn=lambda unit: (
            unit.frost_protection.enabled if unit.frost_protection else None
        ),
        turn_on_fn=lambda client, unit: client.set_frost_protection(
            enabled=True,
            min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
            max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
            atw_unit_ids=[unit.id],
        ),
        turn_off_fn=lambda client, unit: client.set_frost_protection(
            enabled=False,
            min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
            max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
            atw_unit_ids=[unit.id],
        ),
    ),
    ATWSwitchEntityDescription(
        key="overheat_protection",
        translation_key="overheat_protection",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        available_fn=lambda unit: unit.overheat_protection is not None,
        is_on_fn=lambda unit: (
            unit.overheat_protection.enabled if unit.overheat_protection else None
        ),
        turn_on_fn=lambda client, unit: client.set_overheat_protection(
            enabled=True,
            min_temp=unit.overheat_protection.min if unit.overheat_protection else 0.0,
            max_temp=unit.overheat_protection.max if unit.overheat_protection else 0.0,
            atw_unit_ids=[unit.id],
        ),
        turn_off_fn=lambda client, unit: client.set_overheat_protection(
            enabled=False,
            min_temp=unit.overheat_protection.min if unit.overheat_protection else 0.0,
            max_temp=unit.overheat_protection.max if unit.overheat_protection else 0.0,
            atw_unit_ids=[unit.id],
        ),
    ),
)


async def _perform_action(
    coordinator: MelCloudHomeCoordinator,
    coroutine: Coroutine[Any, Any, None],
) -> None:
    """Perform a MELCloud Home action with error handling and coordinator refresh."""
    try:
        await coroutine
    except MelCloudHomeAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except MelCloudHomeConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except MelCloudHomeTimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="timeout_connect",
        ) from err
    else:
        await coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home switches."""
    coordinator = entry.runtime_data

    def _async_add_new_ata_units(units: list[ATAUnit]) -> None:
        async_add_entities(
            ATASwitch(coordinator, entity_description, unit)
            for entity_description in ATA_SWITCHES
            for unit in units
        )

    def _async_add_new_atw_units(units: list[ATWUnit]) -> None:
        async_add_entities(
            ATWSwitch(coordinator, entity_description, unit)
            for entity_description in ATW_SWITCHES
            for unit in units
        )

    coordinator.new_ata_callbacks.append(_async_add_new_ata_units)
    coordinator.new_atw_callbacks.append(_async_add_new_atw_units)

    _async_add_new_ata_units(list(coordinator.ata_units.values()))
    _async_add_new_atw_units(list(coordinator.atw_units.values()))


class ATASwitch(MelCloudHomeATAUnitEntity, SwitchEntity):
    """Representation of a MELCloud Home ATA switch."""

    entity_description: ATASwitchEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATASwitchEntityDescription,
        unit: ATAUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(self.unit)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self.unit)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the protection."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_on_fn(self.coordinator.client, self.unit),
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the protection."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_off_fn(self.coordinator.client, self.unit),
        )


class ATWSwitch(MelCloudHomeATWUnitEntity, SwitchEntity):
    """Representation of a MELCloud Home ATW switch."""

    entity_description: ATWSwitchEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATWSwitchEntityDescription,
        unit: ATWUnit,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        self.entity_description = entity_description
        self._attr_unique_id = f"{unit.id}_{entity_description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(self.unit)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self.unit)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the protection."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_on_fn(self.coordinator.client, self.unit),
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the protection."""
        await _perform_action(
            self.coordinator,
            self.entity_description.turn_off_fn(self.coordinator.client, self.unit),
        )
