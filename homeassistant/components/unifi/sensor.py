"""Sensor platform for UniFi Network integration.

Support for bandwidth sensors of network clients.
Support for uptime sensors of network clients.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic, TypeVar

import aiounifi
from aiounifi.interfaces.api_handlers import CallbackType, ItemEvent, UnsubscribeType
from aiounifi.interfaces.clients import Clients
from aiounifi.models.client import Client

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController
from .unifi_client import UniFiClient

RX_SENSOR = "rx"
TX_SENSOR = "tx"
UPTIME_SENSOR = "uptime"

_DataT = TypeVar("_DataT")
_HandlerT = TypeVar("_HandlerT")
_SubscriptionT = Callable[[CallbackType, ItemEvent], UnsubscribeType]


@callback
def async_client_rx_value_fn(controller: UniFiController, client: Client) -> float:
    """Calculate if all apps are enabled."""
    if client.mac not in controller.wireless_clients:
        return client.wired_rx_bytes_r / 1000000
    return client.rx_bytes_r / 1000000


@callback
def async_client_tx_value_fn(controller: UniFiController, client: Client) -> float:
    """Calculate if all apps are enabled."""
    if client.mac not in controller.wireless_clients:
        return client.wired_tx_bytes_r / 1000000
    return client.tx_bytes_r / 1000000


@callback
def async_client_device_info_fn(api: aiounifi.Controller, obj_id: str) -> DeviceInfo:
    """Create device registry entry for client."""
    client = api.clients[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, obj_id)},
        default_manufacturer=client.oui,
        default_name=client.name or client.hostname,
    )


@dataclass
class UnifiEntityLoader(Generic[_HandlerT, _DataT]):
    """Validate and load entities from different UniFi handlers."""

    allowed_fn: Callable[[UniFiController, str], bool]
    api_handler_fn: Callable[[aiounifi.Controller], _HandlerT]
    available_fn: Callable[[UniFiController, str], bool]
    device_info_fn: Callable[[aiounifi.Controller, str], DeviceInfo]
    name_fn: Callable[[_DataT], str | None]
    object_fn: Callable[[aiounifi.Controller, str], _DataT]
    supported_fn: Callable[[UniFiController, str], bool | None]
    unique_id_fn: Callable[[str], str]
    value_fn: Callable[[UniFiController, _DataT], float]


@dataclass
class UnifiEntityDescription(
    SensorEntityDescription, UnifiEntityLoader[_HandlerT, _DataT]
):
    """Class describing UniFi sensor entity."""


ENTITY_DESCRIPTIONS: tuple[UnifiEntityDescription, ...] = (
    UnifiEntityDescription[Clients, Client](
        key="Bandwidth sensor RX",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        has_entity_name=True,
        allowed_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, _: controller.available,
        device_info_fn=async_client_device_info_fn,
        name_fn=lambda _: "RX",
        object_fn=lambda api, obj_id: api.clients[obj_id],
        supported_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        unique_id_fn=lambda obj_id: f"rx-{obj_id}",
        value_fn=async_client_rx_value_fn,
    ),
    UnifiEntityDescription[Clients, Client](
        key="Bandwidth sensor TX",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        has_entity_name=True,
        allowed_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, _: controller.available,
        device_info_fn=async_client_device_info_fn,
        name_fn=lambda _: "TX",
        object_fn=lambda api, obj_id: api.clients[obj_id],
        supported_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        unique_id_fn=lambda obj_id: f"tx-{obj_id}",
        value_fn=async_client_tx_value_fn,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Network integration."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {
        RX_SENSOR: set(),
        TX_SENSOR: set(),
        UPTIME_SENSOR: set(),
    }

    @callback
    def items_added(
        clients: set = controller.api.clients, devices: set = controller.api.devices
    ) -> None:
        """Update the values of the controller."""
        if controller.option_allow_uptime_sensors:
            add_uptime_entities(controller, async_add_entities, clients)

    for signal in (controller.signal_update, controller.signal_options_update):
        config_entry.async_on_unload(
            async_dispatcher_connect(hass, signal, items_added)
        )

    items_added()

    @callback
    def async_load_entities(description: UnifiEntityDescription) -> None:
        """Load and subscribe to UniFi devices."""
        entities: list[SensorEntity] = []
        api_handler = description.api_handler_fn(controller.api)

        @callback
        def async_create_entity(event: ItemEvent, obj_id: str) -> None:
            """Create UniFi entity."""
            if not description.allowed_fn(
                controller, obj_id
            ) or not description.supported_fn(controller, obj_id):
                return

            entity = UnifiSensorEntity(obj_id, controller, description)
            if event == ItemEvent.ADDED:
                async_add_entities([entity])
                return
            entities.append(entity)

        for obj_id in api_handler:
            async_create_entity(ItemEvent.CHANGED, obj_id)
        async_add_entities(entities)

        api_handler.subscribe(async_create_entity, ItemEvent.ADDED)

    for description in ENTITY_DESCRIPTIONS:
        async_load_entities(description)


@callback
def add_uptime_entities(controller, async_add_entities, clients):
    """Add new sensor entities from the controller."""
    sensors = []

    for mac in clients:
        if mac in controller.entities[DOMAIN][UniFiUpTimeSensor.TYPE]:
            continue

        client = controller.api.clients[mac]
        sensors.append(UniFiUpTimeSensor(client, controller))

    async_add_entities(sensors)


class UniFiUpTimeSensor(UniFiClient, SensorEntity):
    """UniFi Network client uptime sensor."""

    DOMAIN = DOMAIN
    TYPE = UPTIME_SENSOR

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client, controller):
        """Set up tracked client."""
        super().__init__(client, controller)

        self.last_updated_time = self.client.uptime

    @callback
    def async_update_callback(self) -> None:
        """Update sensor when time has changed significantly.

        This will help avoid unnecessary updates to the state machine.
        """
        update_state = True

        if self.client.uptime < 1000000000:
            if self.client.uptime > self.last_updated_time:
                update_state = False
        else:
            if self.client.uptime <= self.last_updated_time:
                update_state = False

        self.last_updated_time = self.client.uptime

        if not update_state:
            return

        super().async_update_callback()

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{super().name} {self.TYPE.capitalize()}"

    @property
    def native_value(self) -> datetime:
        """Return the uptime of the client."""
        if self.client.uptime < 1000000000:
            return dt_util.now() - timedelta(seconds=self.client.uptime)
        return dt_util.utc_from_timestamp(float(self.client.uptime))

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_allow_uptime_sensors:
            await self.remove_item({self.client.mac})


class UnifiSensorEntity(SensorEntity):
    """Base representation of a UniFi switch."""

    entity_description: UnifiEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        obj_id: str,
        controller: UniFiController,
        description: UnifiEntityDescription,
    ) -> None:
        """Set up UniFi switch entity."""
        self._obj_id = obj_id
        self.controller = controller
        self.entity_description = description

        self._removed = False

        self._attr_available = description.available_fn(controller, obj_id)
        self._attr_device_info = description.device_info_fn(controller.api, obj_id)
        self._attr_unique_id = description.unique_id_fn(obj_id)

        obj = description.object_fn(controller.api, obj_id)
        self._attr_native_value = description.value_fn(controller, obj)
        self._attr_name = description.name_fn(obj)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        description = self.entity_description
        handler = description.api_handler_fn(self.controller.api)
        self.async_on_remove(
            handler.subscribe(
                self.async_signalling_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_options_update,
                self.options_updated,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_remove,
                self.remove_item,
            )
        )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the switch state."""
        if event == ItemEvent.DELETED and obj_id == self._obj_id:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        description = self.entity_description
        if not description.supported_fn(self.controller, self._obj_id):
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        obj = description.object_fn(self.controller.api, self._obj_id)
        self._attr_native_value = description.value_fn(self.controller, obj)
        self._attr_available = description.available_fn(self.controller, self._obj_id)
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.entity_description.allowed_fn(self.controller, self._obj_id):
            await self.remove_item({self._obj_id})

    async def remove_item(self, keys: set) -> None:
        """Remove entity if object ID is part of set."""
        if self._obj_id not in keys or self._removed:
            return
        self._removed = True
        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)
