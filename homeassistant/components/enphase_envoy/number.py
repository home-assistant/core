"""Number platform for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyenphase import EnvoyDryContactSettings

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity


@dataclass
class EnvoyRelayRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyDryContactSettings], float]


@dataclass
class EnvoyRelayNumberEntityDescription(
    NumberEntityDescription, EnvoyRelayRequiredKeysMixin
):
    """Describes an Envoy Dry Contact Relay number entity."""


RELAY_ENTITIES = (
    EnvoyRelayNumberEntityDescription(
        key="soc_low",
        translation_key="cutoff_battery_level",
        device_class=NumberDeviceClass.BATTERY,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda relay: relay.soc_low,
    ),
    EnvoyRelayNumberEntityDescription(
        key="soc_high",
        translation_key="restore_battery_level",
        device_class=NumberDeviceClass.BATTERY,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda relay: relay.soc_high,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Enphase Envoy number platform."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    entities: list[NumberEntity] = []
    if envoy_data.dry_contact_settings:
        entities.extend(
            EnvoyRelayNumberEntity(coordinator, entity, relay)
            for entity in RELAY_ENTITIES
            for relay in envoy_data.dry_contact_settings
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
