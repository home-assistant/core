"""Sensor platform for UniFi Network integration.

Support for bandwidth sensors of network clients.
Support for uptime sensors of network clients.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Generic

from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.clients import Clients
from aiounifi.interfaces.devices import Devices
from aiounifi.interfaces.outlets import Outlets
from aiounifi.interfaces.ports import Ports
from aiounifi.interfaces.wlans import Wlans
from aiounifi.models.api import ApiItemT
from aiounifi.models.client import Client
from aiounifi.models.device import Device
from aiounifi.models.outlet import Outlet
from aiounifi.models.port import Port
from aiounifi.models.wlan import Wlan

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfDataRate, UnitOfPower
from homeassistant.core import Event as core_Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import DEVICE_STATES
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
def async_bandwidth_sensor_allowed_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if client is allowed."""
    if obj_id in controller.option_supported_clients:
        return True
    return controller.option_allow_bandwidth_sensors


@callback
def async_uptime_sensor_allowed_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if client is allowed."""
    if obj_id in controller.option_supported_clients:
        return True
    return controller.option_allow_uptime_sensors


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


@callback
def async_device_uptime_value_fn(
    controller: UniFiController, device: Device
) -> datetime | None:
    """Calculate the approximate time the device started (based on uptime returned from API, in seconds)."""
    if device.uptime <= 0:
        # Library defaults to 0 if uptime is not provided, e.g. when offline
        return None
    return (dt_util.now() - timedelta(seconds=device.uptime)).replace(microsecond=0)


@callback
def async_device_uptime_value_changed_fn(
    old: StateType | date | datetime | Decimal, new: datetime | float | str | None
) -> bool:
    """Reject the new uptime value if it's too similar to the old one. Avoids unwanted fluctuation."""
    if isinstance(old, datetime) and isinstance(new, datetime):
        return new != old and abs((new - old).total_seconds()) > 120
    return old is None or (new != old)


@callback
def async_device_outlet_power_supported_fn(
    controller: UniFiController, obj_id: str
) -> bool:
    """Determine if an outlet has the power property."""
    # At this time, an outlet_caps value of 3 is expected to indicate that the outlet
    # supports metering
    return controller.api.outlets[obj_id].caps == 3


@callback
def async_device_outlet_supported_fn(controller: UniFiController, obj_id: str) -> bool:
    """Determine if a device supports reading overall power metrics."""
    return controller.api.devices[obj_id].outlet_ac_power_budget is not None


@callback
def async_client_is_connected_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if client was last seen recently."""
    client = controller.api.clients[obj_id]

    if (
        dt_util.utcnow() - dt_util.utc_from_timestamp(client.last_seen or 0)
        > controller.option_detection_time
    ):
        return False

    return True


@dataclass(frozen=True)
class UnifiSensorEntityDescriptionMixin(Generic[HandlerT, ApiItemT]):
    """Validate and load entities from different UniFi handlers."""

    value_fn: Callable[[UniFiController, ApiItemT], datetime | float | str | None]


@callback
def async_device_state_value_fn(controller: UniFiController, device: Device) -> str:
    """Retrieve the state of the device."""
    return DEVICE_STATES[device.state]


@dataclass(frozen=True)
class UnifiSensorEntityDescription(
    SensorEntityDescription,
    UnifiEntityDescription[HandlerT, ApiItemT],
    UnifiSensorEntityDescriptionMixin[HandlerT, ApiItemT],
):
    """Class describing UniFi sensor entity."""

    is_connected_fn: Callable[[UniFiController, str], bool] | None = None
    # Custom function to determine whether a state change should be recorded
    value_changed_fn: Callable[
        [StateType | date | datetime | Decimal, datetime | float | str | None],
        bool,
    ] = lambda old, new: old != new


ENTITY_DESCRIPTIONS: tuple[UnifiSensorEntityDescription, ...] = (
    UnifiSensorEntityDescription[Clients, Client](
        key="Bandwidth sensor RX",
        device_class=SensorDeviceClass.DATA_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        icon="mdi:upload",
        has_entity_name=True,
        allowed_fn=async_bandwidth_sensor_allowed_fn,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, _: controller.available,
        device_info_fn=async_client_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_connected_fn=async_client_is_connected_fn,
        name_fn=lambda _: "RX",
        object_fn=lambda api, obj_id: api.clients[obj_id],
        should_poll=False,
        supported_fn=lambda controller, _: controller.option_allow_bandwidth_sensors,
        unique_id_fn=lambda controller, obj_id: f"rx-{obj_id}",
        value_fn=async_client_rx_value_fn,
    ),
    UnifiSensorEntityDescription[Clients, Client](
        key="Bandwidth sensor TX",
        device_class=SensorDeviceClass.DATA_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        icon="mdi:download",
        has_entity_name=True,
        allowed_fn=async_bandwidth_sensor_allowed_fn,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, _: controller.available,
        device_info_fn=async_client_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_connected_fn=async_client_is_connected_fn,
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
        key="Client uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
        entity_registry_enabled_default=False,
        allowed_fn=async_uptime_sensor_allowed_fn,
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
        state_class=SensorStateClass.MEASUREMENT,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.wlans,
        available_fn=async_wlan_available_fn,
        device_info_fn=async_wlan_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda wlan: None,
        object_fn=lambda api, obj_id: api.wlans[obj_id],
        should_poll=True,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"wlan_clients-{obj_id}",
        value_fn=async_wlan_client_value_fn,
    ),
    UnifiSensorEntityDescription[Outlets, Outlet](
        key="Outlet power metering",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.outlets,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda outlet: f"{outlet.name} Outlet Power",
        object_fn=lambda api, obj_id: api.outlets[obj_id],
        should_poll=True,
        supported_fn=async_device_outlet_power_supported_fn,
        unique_id_fn=lambda controller, obj_id: f"outlet_power-{obj_id}",
        value_fn=lambda _, obj: obj.power if obj.relay_state else "0",
    ),
    UnifiSensorEntityDescription[Devices, Device](
        key="SmartPower AC power budget",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda device: "AC Power Budget",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        supported_fn=async_device_outlet_supported_fn,
        unique_id_fn=lambda controller, obj_id: f"ac_power_budget-{obj_id}",
        value_fn=lambda controller, device: device.outlet_ac_power_budget,
    ),
    UnifiSensorEntityDescription[Devices, Device](
        key="SmartPower AC power consumption",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda device: "AC Power Consumption",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        supported_fn=async_device_outlet_supported_fn,
        unique_id_fn=lambda controller, obj_id: f"ac_power_conumption-{obj_id}",
        value_fn=lambda controller, device: device.outlet_ac_power_consumption,
    ),
    UnifiSensorEntityDescription[Devices, Device](
        key="Device uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda device: "Uptime",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"device_uptime-{obj_id}",
        value_fn=async_device_uptime_value_fn,
        value_changed_fn=async_device_uptime_value_changed_fn,
    ),
    UnifiSensorEntityDescription[Devices, Device](
        key="Device temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda device: "Temperature",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        supported_fn=lambda ctrlr, obj_id: ctrlr.api.devices[obj_id].has_temperature,
        unique_id_fn=lambda controller, obj_id: f"device_temperature-{obj_id}",
        value_fn=lambda ctrlr, device: device.general_temperature,
    ),
    UnifiSensorEntityDescription[Devices, Device](
        key="Device State",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        name_fn=lambda device: "State",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"device_state-{obj_id}",
        value_fn=async_device_state_value_fn,
        options=list(DEVICE_STATES.values()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Network integration."""
    UniFiController.register_platform(
        hass, config_entry, async_add_entities, UnifiSensorEntity, ENTITY_DESCRIPTIONS
    )


class UnifiSensorEntity(UnifiEntity[HandlerT, ApiItemT], SensorEntity):
    """Base representation of a UniFi sensor."""

    entity_description: UnifiSensorEntityDescription[HandlerT, ApiItemT]

    @callback
    def _make_disconnected(self, *_: core_Event) -> None:
        """No heart beat by device.

        Set sensor as unavailable when client device is disconnected
        """
        if self._attr_available:
            self._attr_available = False
            self.async_write_ha_state()

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update native_value.
        """
        description = self.entity_description
        obj = description.object_fn(self.controller.api, self._obj_id)
        # Update the value only if value is considered to have changed relative to its previous state
        if description.value_changed_fn(
            self.native_value, (value := description.value_fn(self.controller, obj))
        ):
            self._attr_native_value = value

        if description.is_connected_fn is not None:
            # Send heartbeat if client is connected
            if description.is_connected_fn(self.controller, self._obj_id):
                self.controller.async_heartbeat(
                    self._attr_unique_id,
                    dt_util.utcnow() + self.controller.option_detection_time,
                )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if self.entity_description.is_connected_fn is not None:
            # Register callback for missed heartbeat
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{self.controller.signal_heartbeat_missed}_{self.unique_id}",
                    self._make_disconnected,
                )
            )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        await super().async_will_remove_from_hass()

        if self.entity_description.is_connected_fn is not None:
            # Remove heartbeat registration
            self.controller.async_heartbeat(self._attr_unique_id)
