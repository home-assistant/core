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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TailscaleEntity
from .const import DOMAIN


@dataclass
class TailscaleBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[TailscaleDevice], bool | None]


@dataclass
class TailscaleBinarySensorEntityDescription(
    BinarySensorEntityDescription, TailscaleBinarySensorEntityDescriptionMixin
):
    """Describes a Tailscale binary sensor entity."""


BINARY_SENSORS: tuple[TailscaleBinarySensorEntityDescription, ...] = (
    TailscaleBinarySensorEntityDescription(
        key="update_available",
        name="Client",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.update_available,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_hair_pinning",
        name="Supports Hairpinning",
        icon="mdi:wan",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.hair_pinning,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_ipv6",
        name="Supports IPv6",
        icon="mdi:wan",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.ipv6,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_pcp",
        name="Supports PCP",
        icon="mdi:wan",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.pcp,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_pmp",
        name="Supports NAT-PMP",
        icon="mdi:wan",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.pmp,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_udp",
        name="Supports UDP",
        icon="mdi:wan",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.udp,
    ),
    TailscaleBinarySensorEntityDescription(
        key="client_supports_upnp",
        name="Supports UPnP",
        icon="mdi:wan",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device: device.client_connectivity.client_supports.upnp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
