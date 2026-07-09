"""Number platform for MELCloud Home."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from aiomelcloudhome import ATAUnit, ATWUnit, MELCloudHome
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import async_setup_unit_entities
from .const import DOMAIN
from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWUnitEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ATANumberEntityDescription(NumberEntityDescription):
    """Class to hold MELCloud Home ATA number description."""

    available_fn: Callable[[ATAUnit], bool]
    value_fn: Callable[[ATAUnit], float | None]
    set_value_fn: Callable[[MELCloudHome, ATAUnit, float], Coroutine[Any, Any, None]]
    validate_fn: Callable[[ATAUnit, float], str | None] | None = None


@dataclass(frozen=True, kw_only=True)
class ATWNumberEntityDescription(NumberEntityDescription):
    """Class to hold MELCloud Home ATW number description."""

    available_fn: Callable[[ATWUnit], bool]
    value_fn: Callable[[ATWUnit], float | None]
    set_value_fn: Callable[[MELCloudHome, ATWUnit, float], Coroutine[Any, Any, None]]
    validate_fn: Callable[[ATWUnit, float], str | None] | None = None


ATA_NUMBERS: tuple[ATANumberEntityDescription, ...] = (
    ATANumberEntityDescription(
        key="frost_protection_min_temp",
        translation_key="frost_protection_min_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0.0,
        native_max_value=30.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.frost_protection is not None and unit.frost_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.frost_protection.min if unit.frost_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_frost_protection(
            enabled=unit.frost_protection.enabled if unit.frost_protection else False,
            min_temp=value,
            max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
            ata_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_min_exceeds_max"
            if unit.frost_protection and value >= unit.frost_protection.max
            else None
        ),
    ),
    ATANumberEntityDescription(
        key="frost_protection_max_temp",
        translation_key="frost_protection_max_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0.0,
        native_max_value=30.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.frost_protection is not None and unit.frost_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.frost_protection.max if unit.frost_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_frost_protection(
            enabled=unit.frost_protection.enabled if unit.frost_protection else False,
            min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
            max_temp=value,
            ata_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_max_below_min"
            if unit.frost_protection and value <= unit.frost_protection.min
            else None
        ),
    ),
    ATANumberEntityDescription(
        key="overheat_protection_min_temp",
        translation_key="overheat_protection_min_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=31.0,
        native_max_value=40.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.overheat_protection is not None and unit.overheat_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.overheat_protection.min if unit.overheat_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_overheat_protection(
            enabled=unit.overheat_protection.enabled
            if unit.overheat_protection
            else False,
            min_temp=value,
            max_temp=unit.overheat_protection.max if unit.overheat_protection else 0.0,
            ata_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_min_exceeds_max"
            if unit.overheat_protection and value >= unit.overheat_protection.max
            else None
        ),
    ),
    ATANumberEntityDescription(
        key="overheat_protection_max_temp",
        translation_key="overheat_protection_max_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=31.0,
        native_max_value=40.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.overheat_protection is not None and unit.overheat_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.overheat_protection.max if unit.overheat_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_overheat_protection(
            enabled=unit.overheat_protection.enabled
            if unit.overheat_protection
            else False,
            min_temp=unit.overheat_protection.min if unit.overheat_protection else 0.0,
            max_temp=value,
            ata_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_max_below_min"
            if unit.overheat_protection and value <= unit.overheat_protection.min
            else None
        ),
    ),
)

ATW_NUMBERS: tuple[ATWNumberEntityDescription, ...] = (
    ATWNumberEntityDescription(
        key="frost_protection_min_temp",
        translation_key="frost_protection_min_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0.0,
        native_max_value=30.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.frost_protection is not None and unit.frost_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.frost_protection.min if unit.frost_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_frost_protection(
            enabled=unit.frost_protection.enabled if unit.frost_protection else False,
            min_temp=value,
            max_temp=unit.frost_protection.max if unit.frost_protection else 0.0,
            atw_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_min_exceeds_max"
            if unit.frost_protection and value >= unit.frost_protection.max
            else None
        ),
    ),
    ATWNumberEntityDescription(
        key="frost_protection_max_temp",
        translation_key="frost_protection_max_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0.0,
        native_max_value=30.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.frost_protection is not None and unit.frost_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.frost_protection.max if unit.frost_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_frost_protection(
            enabled=unit.frost_protection.enabled if unit.frost_protection else False,
            min_temp=unit.frost_protection.min if unit.frost_protection else 0.0,
            max_temp=value,
            atw_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_max_below_min"
            if unit.frost_protection and value <= unit.frost_protection.min
            else None
        ),
    ),
    ATWNumberEntityDescription(
        key="overheat_protection_min_temp",
        translation_key="overheat_protection_min_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=20.0,
        native_max_value=60.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.overheat_protection is not None and unit.overheat_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.overheat_protection.min if unit.overheat_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_overheat_protection(
            enabled=unit.overheat_protection.enabled
            if unit.overheat_protection
            else False,
            min_temp=value,
            max_temp=unit.overheat_protection.max if unit.overheat_protection else 0.0,
            atw_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_min_exceeds_max"
            if unit.overheat_protection and value >= unit.overheat_protection.max
            else None
        ),
    ),
    ATWNumberEntityDescription(
        key="overheat_protection_max_temp",
        translation_key="overheat_protection_max_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        native_min_value=20.0,
        native_max_value=60.0,
        native_step=0.5,
        available_fn=lambda unit: (
            unit.overheat_protection is not None and unit.overheat_protection.enabled
        ),
        value_fn=lambda unit: (
            unit.overheat_protection.max if unit.overheat_protection else None
        ),
        set_value_fn=lambda client, unit, value: client.set_overheat_protection(
            enabled=unit.overheat_protection.enabled
            if unit.overheat_protection
            else False,
            min_temp=unit.overheat_protection.min if unit.overheat_protection else 0.0,
            max_temp=value,
            atw_unit_ids=[unit.id],
        ),
        validate_fn=lambda unit, value: (
            "temperature_max_below_min"
            if unit.overheat_protection and value <= unit.overheat_protection.min
            else None
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
    """Set up MELCloud Home numbers."""

    async_setup_unit_entities(
        entry.runtime_data,
        async_add_entities,
        lambda units: (
            ATANumber(entry.runtime_data, entity_description, unit)
            for entity_description in ATA_NUMBERS
            for unit in units
        ),
        lambda units: (
            ATWNumber(entry.runtime_data, entity_description, unit)
            for entity_description in ATW_NUMBERS
            for unit in units
        ),
    )


class ATANumber(MelCloudHomeATAUnitEntity, NumberEntity):
    """Representation of a MELCloud Home ATA number."""

    entity_description: ATANumberEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATANumberEntityDescription,
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
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.unit)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the protection temperature threshold."""
        if self.entity_description.validate_fn and (
            error_key := self.entity_description.validate_fn(self.unit, value)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_key,
            )
        await _perform_action(
            self.coordinator,
            self.entity_description.set_value_fn(
                self.coordinator.client, self.unit, value
            ),
        )


class ATWNumber(MelCloudHomeATWUnitEntity, NumberEntity):
    """Representation of a MELCloud Home ATW number."""

    entity_description: ATWNumberEntityDescription

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        entity_description: ATWNumberEntityDescription,
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
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.unit)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the protection temperature threshold."""
        if self.entity_description.validate_fn and (
            error_key := self.entity_description.validate_fn(self.unit, value)
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_key,
            )
        await _perform_action(
            self.coordinator,
            self.entity_description.set_value_fn(
                self.coordinator.client, self.unit, value
            ),
        )
