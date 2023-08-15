"""Select platform for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyenphase import EnvoyDryContactSettings

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator
from .entity import EnvoyBaseEntity

_LOGGER = logging.getLogger(__name__)


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
        value_fn=lambda relay: relay.soc_low,
    ),
    EnvoyRelayNumberEntityDescription(
        key="soc_high",
        translation_key="resume_battery_level",
        device_class=NumberDeviceClass.BATTERY,
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
    envoy_serial_num = config_entry.unique_id
    assert envoy_serial_num is not None
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
        relay: str,
    ) -> None:
        """Initialize the Enphase relay select entity."""
        super().__init__(coordinator, description)
        self.envoy = coordinator.envoy
        assert self.envoy is not None
        assert self.data is not None
        self.enpower = self.data.enpower
        assert self.enpower is not None
        self._serial_number = self.enpower.serial_number
        self.relay = self.data.dry_contact_settings[relay]
        self.relay_id = relay
        self._attr_unique_id = (
            f"{self._serial_number}_relay_{relay}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, relay)},
            manufacturer="Enphase",
            model="Dry contact relay",
            name=self.relay.load_name,
            sw_version=str(self.enpower.firmware_version),
            via_device=(DOMAIN, self._serial_number),
        )

    @property
    def native_value(self) -> float:
        """Return the state of the relay entity."""
        return self.entity_description.value_fn(
            self.data.dry_contact_settings[self.relay_id]
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the relay."""
        await self.envoy.update_dry_contact(
            {"id": self.relay.id, self.entity_description.key: int(value)}
        )
        await self.coordinator.async_request_refresh()
