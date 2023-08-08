"""Sensor platform for UniFi Network integration.

Support for bandwidth sensors of network clients.
Support for uptime sensors of network clients.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic

from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.clients import Clients
from aiounifi.interfaces.ports import Ports
from aiounifi.interfaces.wlans import Wlans
from aiounifi.models.api import ApiItemT
from aiounifi.models.client import Client
from aiounifi.models.port import Port
from aiounifi.models.wlan import Wlan

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController
from .entity import (
    HandlerT,
    UnifiEntity,
    UnifiEntityDescription,
    async_client_device_info_fn,
    async_device_available_fn,
    async_device_device_info_fn,
    async_wlan_available_fn,
    async_wlan_device_info_fn,
)


@callback
def async_client_rx_value_fn(controller: UniFiController, client: Client) -> float:
    """Calculate receiving data transfer value."""
    if controller.wireless_clients.is_wireless(client):
        return client.rx_bytes_r / 1000000
    return client.wired_rx_bytes_r / 1000000


@callback
def async_client_tx_value_fn(controller: UniFiController, client: Client) -> float:
    """Calculate transmission data transfer value."""
    if controller.wireless_clients.is_wireless(client):
        return client.tx_bytes_r / 1000000
    return client.wired_tx_bytes_r / 1000000


@callback
def async_client_uptime_value_fn(
    controller: UniFiController, client: Client
) -> datetime:
    """Calculate the uptime of the client."""
    if client.uptime < 1000000000:
        return dt_util.now() - timedelta(seconds=client.uptime)
    return dt_util.utc_from_timestamp(float(client.uptime))


@callback
def async_wlan_client_value_fn(controller: UniFiController, wlan: Wlan) -> int:
    """Calculate the amount of clients connected to a wlan."""
    return len(
        [
            client.mac
            for client in controller.api.clients.values()
            if client.essid == wlan.name
            and dt_util.utcnow() - dt_util.utc_from_timestamp(client.last_seen or 0)
            < controller.option_detection_time
        ]
    )


@dataclass
class UnifiSensorEntityDescriptionMixin(Generic[HandlerT, ApiItemT]):
    """Validate and load entities from different UniFi handlers."""

    value_fn: Callable[[UniFiController, ApiItemT], datetime | float | str | None]


@dataclass
class UnifiSensorEntityDescription(
    SensorEntityDescription,
    UnifiEntityDescription[HandlerT, ApiItemT],
    UnifiSensorEntityDescriptionMixin[HandlerT, ApiItemT],
):
    """Class describing UniFi sensor entity."""


ENTITY_DESCRIPTIONS: tuple[UnifiSensorEntityDescription, ...] = (
    UnifiSensorEntityDescription[Clients, Client](
        key="Bandwidth sensor RX",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        has_entity_name=True,
        allowed_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, _: controller.available,
        device_info_fn=async_client_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda _: "RX",
        object_fn=lambda api, obj_id: api.clients[obj_id],
        should_poll=False,
        supported_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        unique_id_fn=lambda controller, obj_id: f"rx-{obj_id}",
        value_fn=async_client_rx_value_fn,
    ),
    UnifiSensorEntityDescription[Clients, Client](
        key="Bandwidth sensor TX",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        has_entity_name=True,
        allowed_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, _: controller.available,
        device_info_fn=async_client_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda _: "TX",
        object_fn=lambda api, obj_id: api.clients[obj_id],
        should_poll=False,
        supported_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        unique_id_fn=lambda controller, obj_id: f"tx-{obj_id}",
        value_fn=async_client_tx_value_fn,
    ),
    UnifiSensorEntityDescription[Ports, Port](
        key="PoE port power sensor",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        has_entity_name=True,
        entity_registry_enabled_default=False,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.ports,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda port: f"{port.name} PoE Power",
        object_fn=lambda api, obj_id: api.ports[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: controller.api.ports[obj_id].port_poe,
        unique_id_fn=lambda controller, obj_id: f"poe_power-{obj_id}",
        value_fn=lambda _, obj: obj.poe_power if obj.poe_mode != "off" else "0",
    ),
    UnifiSensorEntityDescription[Clients, Client](
        key="Uptime sensor",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
        entity_registry_enabled_default=False,
        allowed_fn=lambda controller, _: controller.option_allow_uptime_sensors,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, obj_id: controller.available,
        device_info_fn=async_client_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda client: "Uptime",
        object_fn=lambda api, obj_id: api.clients[obj_id],
        should_poll=False,
        supported_fn=lambda controller, _: controller.option_allow_uptime_sensors,
        unique_id_fn=lambda controller, obj_id: f"uptime-{obj_id}",
        value_fn=async_client_uptime_value_fn,
    ),
    UnifiSensorEntityDescription[Wlans, Wlan](
        key="WLAN clients",
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
        allowed_fn=lambda controller, _: True,
        api_handler_fn=lambda api: api.wlans,
        available_fn=async_wlan_available_fn,
        device_info_fn=async_wlan_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda client: None,
        object_fn=lambda api, obj_id: api.wlans[obj_id],
        should_poll=True,
        supported_fn=lambda controller, _: True,
        unique_id_fn=lambda controller, obj_id: f"wlan_clients-{obj_id}",
        value_fn=async_wlan_client_value_fn,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Network integration."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.register_platform_add_entities(
        UnifiSensorEntity, ENTITY_DESCRIPTIONS, async_add_entities
    )


class UnifiSensorEntity(UnifiEntity[HandlerT, ApiItemT], SensorEntity):
    """Base representation of a UniFi sensor."""

    entity_description: UnifiSensorEntityDescription[HandlerT, ApiItemT]

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update native_value.
        """
        description = self.entity_description
        obj = description.object_fn(self.controller.api, self._obj_id)
        if (value := description.value_fn(self.controller, obj)) != self.native_value:
            self._attr_native_value = value
