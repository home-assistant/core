"""Lock platform for Tessie integration."""

from __future__ import annotations

from typing import Any

from tessie_api import (
    disable_speed_limit,
    enable_speed_limit,
    lock,
    open_unlock_charge_port,
    unlock,
)

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.lock import ATTR_CODE, LockEntity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TessieConfigEntry
from .const import DOMAIN, TessieChargeCableLockStates
from .entity import TessieEntity
from .models import TessieVehicleData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    data = entry.runtime_data

    entities: list[TessieEntity] = [
        klass(vehicle)
        for klass in (TessieLockEntity, TessieCableLockEntity)
        for vehicle in data.vehicles
    ]

    ent_reg = er.async_get(hass)

    for vehicle in data.vehicles:
        entity_id = ent_reg.async_get_entity_id(
            Platform.LOCK,
            DOMAIN,
            f"{vehicle.vin}-vehicle_state_speed_limit_mode_active",
        )
        if entity_id:
            entity_entry = ent_reg.async_get(entity_id)
            assert entity_entry
            if entity_entry.disabled:
                ent_reg.async_remove(entity_id)
            else:
                entities.append(TessieSpeedLimitEntity(vehicle))

                entity_automations = automations_with_entity(hass, entity_id)
                entity_scripts = scripts_with_entity(hass, entity_id)
                for item in entity_automations + entity_scripts:
                    ir.async_create_issue(
                        hass,
                        DOMAIN,
                        f"deprecated_speed_limit_{entity_id}_{item}",
                        breaks_in_ha_version="2024.11.0",
                        is_fixable=True,
                        is_persistent=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="deprecated_speed_limit_entity",
                        translation_placeholders={
                            "entity": entity_id,
                            "info": item,
                        },
                    )
    async_add_entities(entities)


class TessieLockEntity(TessieEntity, LockEntity):
    """Lock entity for Tessie."""

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_locked")

    @property
    def is_locked(self) -> bool | None:
        """Return the state of the Lock."""
        return self._value

    async def async_lock(self, **kwargs: Any) -> None:
        """Set new value."""
        await self.run(lock)
        self.set((self.key, True))

    async def async_unlock(self, **kwargs: Any) -> None:
        """Set new value."""
        await self.run(unlock)
        self.set((self.key, False))


class TessieSpeedLimitEntity(TessieEntity, LockEntity):
    """Speed Limit with PIN entity for Tessie."""

    _attr_code_format = r"^\d\d\d\d$"

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_speed_limit_mode_active")

    @property
    def is_locked(self) -> bool | None:
        """Return the state of the Lock."""
        return self._value

    async def async_lock(self, **kwargs: Any) -> None:
        """Enable speed limit with pin."""
        ir.async_create_issue(
            self.coordinator.hass,
            DOMAIN,
            "deprecated_speed_limit_locked",
            breaks_in_ha_version="2024.11.0",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_speed_limit_locked",
        )
        code: str | None = kwargs.get(ATTR_CODE)
        if code:
            await self.run(enable_speed_limit, pin=code)
            self.set((self.key, True))

    async def async_unlock(self, **kwargs: Any) -> None:
        """Disable speed limit with pin."""
        ir.async_create_issue(
            self.coordinator.hass,
            DOMAIN,
            "deprecated_speed_limit_unlocked",
            breaks_in_ha_version="2024.11.0",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_speed_limit_unlocked",
        )
        code: str | None = kwargs.get(ATTR_CODE)
        if code:
            await self.run(disable_speed_limit, pin=code)
            self.set((self.key, False))


class TessieCableLockEntity(TessieEntity, LockEntity):
    """Cable Lock entity for Tessie."""

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "charge_state_charge_port_latch")

    @property
    def is_locked(self) -> bool | None:
        """Return the state of the Lock."""
        return self._value == TessieChargeCableLockStates.ENGAGED

    async def async_lock(self, **kwargs: Any) -> None:
        """Charge cable Lock cannot be manually locked."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_cable",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock charge cable lock."""
        await self.run(open_unlock_charge_port)
        self.set((self.key, TessieChargeCableLockStates.DISENGAGED))
