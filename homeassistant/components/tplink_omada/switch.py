"""Support for TPLink Omada device toggle options."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, Generic, TypeVar

from tplink_omada_client import (
    GatewayPortSettings,
    OmadaSiteClient,
    PortProfileOverrides,
    SwitchPortSettings,
)
from tplink_omada_client.definitions import (
    DeviceStatusCategory,
    GatewayPortMode,
    PoEMode,
    PortType,
)
from tplink_omada_client.devices import (
    OmadaDevice,
    OmadaGateway,
    OmadaGatewayPortConfig,
    OmadaGatewayPortStatus,
    OmadaListDevice,
    OmadaSwitch,
    OmadaSwitchPortDetails,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OmadaConfigEntry
from .controller import OmadaGatewayCoordinator, OmadaSwitchPortCoordinator
from .coordinator import OmadaCoordinator
from .entity import OmadaDeviceEntity

TPort = TypeVar("TPort")
TDevice = TypeVar("TDevice", bound="OmadaDevice")
TCoordinator = TypeVar("TCoordinator", bound="OmadaCoordinator[Any]")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    controller = config_entry.runtime_data

    async def _create_switch_port_entities(
        device: OmadaListDevice,
    ) -> None:
        """Create entities for a switch's ports."""
        omada_client = controller.omada_client
        switch = await omada_client.get_switch(device)
        coordinator = controller.get_switch_port_coordinator(switch)
        await coordinator.async_request_refresh()

        entities: list[Entity] = []
        entities.extend(
            OmadaDevicePortSwitchEntity[
                OmadaSwitchPortCoordinator, OmadaSwitch, OmadaSwitchPortDetails
            ](
                coordinator,
                switch,
                port,
                port.port_id,
                desc,
                port_name=_get_switch_port_base_name(port),
            )
            for port in coordinator.data.values()
            for desc in SWITCH_PORT_DETAILS_SWITCHES
            if desc.exists_func(switch, port)
        )
        async_add_entities(entities)

    # Register switch port entities for switches that are connected, such that we can determine the port information
    await controller.async_register_device_entities(
        device_filter=lambda d: (
            d.type == "switch" and d.status_category == DeviceStatusCategory.CONNECTED
        ),
        entity_callback=_create_switch_port_entities,
    )

    # Set up gateway port switches
    async def _create_gateway_port_entities(
        device: OmadaListDevice,
    ) -> None:
        """Create entities for a gateway's ports."""
        entities: list[Entity] = []
        gateway_coordinator = controller.gateway_coordinator
        if gateway_coordinator:
            gateway = gateway_coordinator.data[device.mac]
            entities.extend(
                OmadaDevicePortSwitchEntity[
                    OmadaGatewayCoordinator, OmadaGateway, OmadaGatewayPortStatus
                ](gateway_coordinator, gateway, p, str(p.port_number), desc)
                for p in gateway.port_status
                for desc in GATEWAY_PORT_STATUS_SWITCHES
                if desc.exists_func(gateway, p)
            )
            entities.extend(
                OmadaDevicePortSwitchEntity[
                    OmadaGatewayCoordinator, OmadaGateway, OmadaGatewayPortConfig
                ](gateway_coordinator, gateway, p, str(p.port_number), desc)
                for p in gateway.port_configs
                for desc in GATEWAY_PORT_CONFIG_SWITCHES
                if desc.exists_func(gateway, p)
            )
        async_add_entities(entities)

    await controller.async_register_device_entities(
        device_filter=lambda d: (
            d.type == "gateway" and d.status_category == DeviceStatusCategory.CONNECTED
        ),
        entity_callback=_create_gateway_port_entities,
    )


def _get_switch_port_base_name(port: OmadaSwitchPortDetails) -> str:
    """Get display name for a switch port."""

    if port.name == f"Port{port.port}":
        return str(port.port)
    return f"{port.port} ({port.name})"


@dataclass(frozen=True, kw_only=True)
class OmadaDevicePortSwitchEntityDescription(
    SwitchEntityDescription, Generic[TCoordinator, TDevice, TPort]
):
    """Entity description for a toggle switch derived from a network port on an Omada device."""

    exists_func: Callable[[TDevice, TPort], bool] = lambda _, p: True
    coordinator_update_func: Callable[[TCoordinator, TDevice, TPort], TPort | None]
    set_func: Callable[[OmadaSiteClient, TDevice, TPort, bool], Awaitable[TPort | None]]
    update_func: Callable[[TPort], bool]


@dataclass(frozen=True, kw_only=True)
class OmadaSwitchPortSwitchEntityDescription(
    OmadaDevicePortSwitchEntityDescription[
        OmadaSwitchPortCoordinator, OmadaSwitch, OmadaSwitchPortDetails
    ]
):
    """Entity description for a toggle switch for a feature of a Port on an Omada Switch."""

    coordinator_update_func: Callable[
        [OmadaSwitchPortCoordinator, OmadaSwitch, OmadaSwitchPortDetails],
        OmadaSwitchPortDetails | None,
    ] = lambda coord, _, port: coord.data.get(port.port_id)


@dataclass(frozen=True, kw_only=True)
class OmadaGatewayPortConfigSwitchEntityDescription(
    OmadaDevicePortSwitchEntityDescription[
        OmadaGatewayCoordinator, OmadaGateway, OmadaGatewayPortConfig
    ]
):
    """Entity description for a toggle switch for a configuration of a Port on an Omada Gateway."""

    coordinator_update_func: Callable[
        [OmadaGatewayCoordinator, OmadaGateway, OmadaGatewayPortConfig],
        OmadaGatewayPortConfig | None,
    ] = lambda coord, device, port: next(
        p
        for p in coord.data[device.mac].port_configs
        if p.port_number == port.port_number
    )


@dataclass(frozen=True, kw_only=True)
class OmadaGatewayPortStatusSwitchEntityDescription(
    OmadaDevicePortSwitchEntityDescription[
        OmadaGatewayCoordinator, OmadaGateway, OmadaGatewayPortStatus
    ]
):
    """Entity description for a toggle switch for a status of a Port on an Omada Gateway."""

    coordinator_update_func: Callable[
        [OmadaGatewayCoordinator, OmadaGateway, OmadaGatewayPortStatus],
        OmadaGatewayPortStatus,
    ] = lambda coord, device, port: next(
        p
        for p in coord.data[device.mac].port_status
        if p.port_number == port.port_number
    )


async def _wan_connect_disconnect(
    client: OmadaSiteClient,
    device: OmadaDevice,
    port: OmadaGatewayPortStatus,
    enable: bool,
    ipv6: bool,
) -> None:
    # The state returned by the API is not valid. By returning None, we force a refresh
    await client.set_gateway_wan_port_connect_state(
        port.port_number, enable, device, ipv6=ipv6
    )


SWITCH_PORT_DETAILS_SWITCHES: list[OmadaSwitchPortSwitchEntityDescription] = [
    OmadaSwitchPortSwitchEntityDescription(
        key="poe",
        translation_key="poe_control",
        exists_func=(
            lambda d, p: d.device_capabilities.supports_poe
            and p.supports_poe
            and p.type != PortType.SFP
        ),
        set_func=(
            lambda client, device, port, enable: client.update_switch_port(
                device,
                port,
                settings=SwitchPortSettings(
                    profile_override_enabled=True,
                    profile_overrides=PortProfileOverrides(enable_poe=enable),
                ),
            )
        ),
        update_func=lambda p: p.poe_mode != PoEMode.DISABLED,
        entity_category=EntityCategory.CONFIG,
    )
]

GATEWAY_PORT_STATUS_SWITCHES: list[OmadaGatewayPortStatusSwitchEntityDescription] = [
    OmadaGatewayPortStatusSwitchEntityDescription(
        key="wan_connect_ipv4",
        translation_key="wan_connect_ipv4",
        exists_func=lambda _, p: p.mode == GatewayPortMode.WAN,
        set_func=partial(_wan_connect_disconnect, ipv6=False),
        update_func=lambda p: p.wan_connected,
    ),
    OmadaGatewayPortStatusSwitchEntityDescription(
        key="wan_connect_ipv6",
        translation_key="wan_connect_ipv6",
        exists_func=lambda _, p: p.mode == GatewayPortMode.WAN and p.wan_ipv6_enabled,
        set_func=partial(_wan_connect_disconnect, ipv6=True),
        update_func=lambda p: p.ipv6_wan_connected,
    ),
]

GATEWAY_PORT_CONFIG_SWITCHES: list[OmadaGatewayPortConfigSwitchEntityDescription] = [
    OmadaGatewayPortConfigSwitchEntityDescription(
        key="poe",
        translation_key="poe_control",
        exists_func=lambda _, port: port.poe_mode != PoEMode.NONE,
        set_func=lambda client, device, port, enable: client.set_gateway_port_settings(
            port.port_number, GatewayPortSettings(enable_poe=enable), device
        ),
        update_func=lambda p: p.poe_mode != PoEMode.DISABLED,
    ),
]


class OmadaDevicePortSwitchEntity(
    OmadaDeviceEntity[TCoordinator],
    SwitchEntity,
    Generic[TCoordinator, TDevice, TPort],
):
    """Generic toggle switch entity for a Netork Port of an Omada Device."""

    entity_description: OmadaDevicePortSwitchEntityDescription[
        TCoordinator, TDevice, TPort
    ]

    def __init__(
        self,
        coordinator: TCoordinator,
        device: TDevice,
        port_details: TPort,
        port_id: str,
        entity_description: OmadaDevicePortSwitchEntityDescription[
            TCoordinator, TDevice, TPort
        ],
        port_name: str | None = None,
    ) -> None:
        """Initialize the toggle switch."""
        super().__init__(coordinator, device)
        self.entity_description = entity_description
        self._device = device
        self._port_details = port_details
        self._attr_unique_id = f"{device.mac}_{port_id}_{entity_description.key}"
        self._attr_translation_placeholders = {"port_name": port_name or port_id}

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._do_update()

    async def _async_turn_on_off(self, enable: bool) -> None:
        updated_details = await self.entity_description.set_func(
            self.coordinator.omada_client, self._device, self._port_details, enable
        )

        if updated_details:
            self._port_details = updated_details
            self._attr_is_on = self.entity_description.update_func(self._port_details)
        else:
            self._attr_is_on = enable
            await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_turn_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_turn_on_off(False)

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(
            super().available
            and self._port_details
            and self.entity_description.exists_func(self._device, self._port_details)
        )

    def _do_update(self) -> None:
        latest_port_details = self.entity_description.coordinator_update_func(
            self.coordinator, self._device, self._port_details
        )
        if latest_port_details:
            self._port_details = latest_port_details
            self._attr_is_on = self.entity_description.update_func(self._port_details)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._do_update()
        self.async_write_ha_state()
