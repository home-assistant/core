"""Support for TPLink Omada device toggle options."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from tplink_omada_client import OmadaSiteClient, SwitchPortOverrides
from tplink_omada_client.definitions import GatewayPortMode, PoEMode
from tplink_omada_client.devices import (
    OmadaDevice,
    OmadaGateway,
    OmadaGatewayPortStatus,
    OmadaSwitch,
    OmadaSwitchPortDetails,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import (
    OmadaGatewayCoordinator,
    OmadaSiteController,
    OmadaSwitchPortCoordinator,
)
from .entity import OmadaDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    controller: OmadaSiteController = hass.data[DOMAIN][config_entry.entry_id]
    omada_client = controller.omada_client

    # Naming fun. Omada switches, as in the network hardware
    network_switches = await omada_client.get_switches()

    entities: list = []
    for switch in [
        ns for ns in network_switches if ns.device_capabilities.supports_poe
    ]:
        coordinator = controller.get_switch_port_coordinator(switch)
        await coordinator.async_request_refresh()

        for idx, port_id in enumerate(coordinator.data):
            if idx < switch.device_capabilities.poe_ports:
                entities.append(
                    OmadaNetworkSwitchPortPoEControl(coordinator, switch, port_id)
                )

    gateway_coordinator = await controller.get_gateway_coordinator()
    if gateway_coordinator:
        for gateway in gateway_coordinator.data.values():
            entities.extend(
                OmadaGatewayPortSwitchEntity(
                    gateway_coordinator, gateway, p.port_number, desc
                )
                for p in gateway.port_status
                for desc in GATEWAY_PORT_SWITCHES
                if desc.exists_func(p)
            )

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class GatewayPortSwitchEntityDescription(SwitchEntityDescription):
    """Entity description for a toggle switch derived from a gateway port."""

    exists_func: Callable[[OmadaGatewayPortStatus], bool] = lambda _: True
    set_func: Callable[
        [OmadaSiteClient, OmadaDevice, OmadaGatewayPortStatus, bool],
        Awaitable[OmadaGatewayPortStatus],
    ]
    update_func: Callable[[OmadaGatewayPortStatus], bool]


def _wan_connect_disconnect(
    client: OmadaSiteClient,
    device: OmadaDevice,
    port: OmadaGatewayPortStatus,
    enable: bool,
    ipv6: bool,
) -> Awaitable[OmadaGatewayPortStatus]:
    return client.set_gateway_wan_port_connect_state(
        port.port_number, enable, device, ipv6=ipv6
    )


GATEWAY_PORT_SWITCHES: list[GatewayPortSwitchEntityDescription] = [
    GatewayPortSwitchEntityDescription(
        key="wan_connect_ipv4",
        translation_key="wan_connect_ipv4",
        exists_func=lambda p: p.mode == GatewayPortMode.WAN,
        set_func=partial(_wan_connect_disconnect, ipv6=False),
        update_func=lambda p: p.wan_connected,
    ),
    GatewayPortSwitchEntityDescription(
        key="wan_connect_ipv6",
        translation_key="wan_connect_ipv6",
        exists_func=lambda p: p.mode == GatewayPortMode.WAN and p.wan_ipv6_enabled,
        set_func=partial(_wan_connect_disconnect, ipv6=True),
        update_func=lambda p: p.ipv6_wan_connected,
    ),
]


def get_port_base_name(port: OmadaSwitchPortDetails) -> str:
    """Get display name for a switch port."""

    if port.name == f"Port{port.port}":
        return f"{port.port}"
    return f"{port.port} ({port.name})"


class OmadaNetworkSwitchPortPoEControl(
    OmadaDeviceEntity[OmadaSwitchPortDetails], SwitchEntity
):
    """Representation of a PoE control toggle on a single network port on a switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "poe_control"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: OmadaSwitchPortCoordinator,
        device: OmadaSwitch,
        port_id: str,
    ) -> None:
        """Initialize the PoE switch."""
        super().__init__(coordinator, device)
        self.port_id = port_id
        self.port_details = coordinator.data[port_id]
        self.omada_client = coordinator.omada_client
        self._attr_unique_id = f"{device.mac}_{port_id}_poe"
        self._attr_translation_placeholders = {
            "port_name": get_port_base_name(self.port_details)
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._refresh_state()

    async def _async_turn_on_off_poe(self, enable: bool) -> None:
        self.port_details = await self.omada_client.update_switch_port(
            self.device,
            self.port_details,
            overrides=SwitchPortOverrides(enable_poe=enable),
        )
        self._refresh_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_turn_on_off_poe(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_turn_on_off_poe(False)

    def _refresh_state(self) -> None:
        self._attr_is_on = self.port_details.poe_mode != PoEMode.DISABLED
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.port_details = self.coordinator.data[self.port_id]
        self._refresh_state()


class OmadaGatewayPortSwitchEntity(OmadaDeviceEntity[OmadaGateway], SwitchEntity):
    """Generic toggle switch on a Gateway entity."""

    _attr_has_entity_name = True
    _port_details: OmadaGatewayPortStatus | None = None
    entity_description: GatewayPortSwitchEntityDescription

    def __init__(
        self,
        coordinator: OmadaGatewayCoordinator,
        device: OmadaGateway,
        port_number: int,
        entity_description: GatewayPortSwitchEntityDescription,
    ) -> None:
        """Initialize the toggle switch."""
        super().__init__(coordinator, device)
        self.entity_description = entity_description
        self._port_number = port_number
        self._attr_unique_id = f"{device.mac}_{port_number}_{entity_description.key}"
        self._attr_translation_placeholders = {"port_name": f"{port_number}"}

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._do_update()

    async def _async_turn_on_off(self, enable: bool) -> None:
        if self._port_details:
            self._port_details = await self.entity_description.set_func(
                self.coordinator.omada_client, self.device, self._port_details, enable
            )
        self._attr_is_on = enable
        # Refresh to make sure the requested changes stuck
        await self.coordinator.async_request_refresh()

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
            and self.entity_description.exists_func(self._port_details)
        )

    def _do_update(self) -> None:
        gateway = self.coordinator.data[self.device.mac]

        port = next(
            p for p in gateway.port_status if p.port_number == self._port_number
        )
        if port:
            self._port_details = port
            self._attr_is_on = self.entity_description.update_func(port)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._do_update()
        self.async_write_ha_state()
