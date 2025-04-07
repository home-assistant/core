"""Support for Tailscale binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tailscale import Device as TailscaleDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import TailscaleEntity


@dataclass(frozen=True, kw_only=True)
class TailscaleBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Tailscale binary sensor entity."""

    is_on_fn: Callable[[TailscaleDevice], bool | None]


BINARY_SENSORS: tuple[TailscaleBinarySensorEntityDescription, ...] = (
    TailscaleBinarySensorEntityDescription(
        key="update_available",
        translation_key="client",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.update_available,
    ),
    TailscaleBinarySensorEntityDescription(
        key="key_expiry_disabled",
        translation_key="key_expiry_disabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.key_expiry_disabled,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_hair_pinning",
        translation_key="client_supports_hair_pinning",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.hair_pinning,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_ipv6",
        translation_key="client_supports_ipv6",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.ipv6,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_pcp",
        translation_key="client_supports_pcp",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.pcp,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_pmp",
        translation_key="client_supports_pmp",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.pmp,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_udp",
        translation_key="client_supports_udp",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.udp,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_upnp",
        translation_key="client_supports_upnp",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.upnp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Tailscale binary sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TailscaleBinarySensorEntity(
            coordinator=coordinator,
            device=device,
            description=description,
        )
        for device in coordinator.data.values()
        for description in BINARY_SENSORS
    )


class TailscaleBinarySensorEntity(TailscaleEntity, BinarySensorEntity):
    """Defines a Tailscale binary sensor."""

    entity_description: TailscaleBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data[self.device_id])
