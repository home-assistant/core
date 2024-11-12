"""Number platform for Enphase Envoy solar energy monitor."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from operator import attrgetter
from typing import Any

from pyenphase import Envoy, EnvoyDryContactSettings
from pyenphase.const import SupportedFeatures
from pyenphase.models.tariff import EnvoyStorageSettings

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity


@dataclass(frozen=True, kw_only=True)
class EnvoyRelayNumberEntityDescription(NumberEntityDescription):
    """Describes an Envoy Dry Contact Relay number entity."""

    value_fn: Callable[[EnvoyDryContactSettings], float]


@dataclass(frozen=True, kw_only=True)
class EnvoyStorageSettingsNumberEntityDescription(NumberEntityDescription):
    """Describes an Envoy storage mode number entity."""

    value_fn: Callable[[EnvoyStorageSettings], float]
    update_fn: Callable[[Envoy, float], Awaitable[dict[str, Any]]]


RELAY_ENTITIES = (
    EnvoyRelayNumberEntityDescription(
        key="soc_low",
        translation_key="cutoff_battery_level",
        device_class=NumberDeviceClass.BATTERY,
        entity_category=EntityCategory.CONFIG,
        value_fn=attrgetter("soc_low"),
    ),
    EnvoyRelayNumberEntityDescription(
        key="soc_high",
        translation_key="restore_battery_level",
        device_class=NumberDeviceClass.BATTERY,
        entity_category=EntityCategory.CONFIG,
        value_fn=attrgetter("soc_high"),
    ),
)

STORAGE_RESERVE_SOC_ENTITY = EnvoyStorageSettingsNumberEntityDescription(
    key="reserve_soc",
    translation_key="reserve_soc",
    native_unit_of_measurement=PERCENTAGE,
    device_class=NumberDeviceClass.BATTERY,
    value_fn=attrgetter("reserved_soc"),
    update_fn=lambda envoy, value: envoy.set_reserve_soc(int(value)),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnphaseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Enphase Envoy number platform."""
    coordinator = config_entry.runtime_data
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    entities: list[NumberEntity] = []
    if envoy_data.dry_contact_settings:
        entities.extend(
            EnvoyRelayNumberEntity(coordinator, entity, relay)
            for entity in RELAY_ENTITIES
            for relay in envoy_data.dry_contact_settings
        )
    if (
        envoy_data.tariff
        and envoy_data.tariff.storage_settings
        and coordinator.envoy.supported_features & SupportedFeatures.ENCHARGE
    ):
        entities.append(
            EnvoyStorageSettingsNumberEntity(coordinator, STORAGE_RESERVE_SOC_ENTITY)
        )
    async_add_entities(entities)


class EnvoyRelayNumberEntity(EnvoyBaseEntity, NumberEntity):
    """Representation of an Enphase Enpower number entity."""

    entity_description: EnvoyRelayNumberEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyRelayNumberEntityDescription,
        relay_id: str,
    ) -> None:
        """Initialize the Enphase relay number entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        enpower = self.data.enpower
        assert enpower is not None
        serial_number = enpower.serial_number
        self._relay_id = relay_id
        self._attr_unique_id = f"{serial_number}_relay_{relay_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, relay_id)},
            manufacturer="Enphase",
            model="Dry contact relay",
            name=self.data.dry_contact_settings[relay_id].load_name,
            sw_version=str(enpower.firmware_version),
            via_device=(DOMAIN, serial_number),
        )

    @property
    def native_value(self) -> float:
        """Return the state of the relay entity."""
        return self.entity_description.value_fn(
            self.data.dry_contact_settings[self._relay_id]
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the relay."""
        await self.envoy.update_dry_contact(
            {"id": self._relay_id, self.entity_description.key: int(value)}
        )
        await self.coordinator.async_request_refresh()


class EnvoyStorageSettingsNumberEntity(EnvoyBaseEntity, NumberEntity):
    """Representation of an Enphase storage settings number entity."""

    entity_description: EnvoyStorageSettingsNumberEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyStorageSettingsNumberEntityDescription,
    ) -> None:
        """Initialize the Enphase relay number entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        assert self.data is not None
        if enpower := self.data.enpower:
            self._serial_number = enpower.serial_number
            self._attr_unique_id = f"{self._serial_number}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._serial_number)},
                manufacturer="Enphase",
                model="Enpower",
                name=f"Enpower {self._serial_number}",
                sw_version=str(enpower.firmware_version),
                via_device=(DOMAIN, self.envoy_serial_num),
            )
        else:
            # If no enpower device assign numbers to Envoy itself
            self._attr_unique_id = f"{self.envoy_serial_num}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.envoy_serial_num)},
                manufacturer="Enphase",
                model=coordinator.envoy.envoy_model,
                name=coordinator.name,
                sw_version=str(coordinator.envoy.firmware),
                hw_version=coordinator.envoy.part_number,
                serial_number=self.envoy_serial_num,
            )

    @property
    def native_value(self) -> float:
        """Return the state of the storage setting entity."""
        assert self.data.tariff is not None
        assert self.data.tariff.storage_settings is not None
        return self.entity_description.value_fn(self.data.tariff.storage_settings)

    async def async_set_native_value(self, value: float) -> None:
        """Update the storage setting."""
        await self.entity_description.update_fn(self.envoy, value)
        await self.coordinator.async_request_refresh()
