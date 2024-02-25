"""Support for TPLink Omada device toggle options."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from attr import dataclass
from tplink_omada_client import OmadaSiteClient, SwitchPortOverrides
from tplink_omada_client.definitions import GatewayPortMode, PoEMode
from tplink_omada_client.devices import (
    OmadaGateway,
    OmadaGatewayPortStatus,
    OmadaSwitch,
    OmadaSwitchPortDetails,
)

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
                get_gateway_port_switch_entities(
                    gateway, gateway_coordinator, omada_client
                )
            )

    async_add_entities(entities)


def get_gateway_port_switch_entities(
    gateway: OmadaGateway,
    coordinator: OmadaGatewayCoordinator,
    omada_client: OmadaSiteClient,
):
    """Get switch entities for the ports on a gateway."""

    for port in gateway.port_status:
        # For WAN ports, create a switch to connect/disconect the port from the internet
        if port.mode == GatewayPortMode.WAN:
            yield OmadaGatewayPortSwitchEntity(
                coordinator,
                gateway,
                GatewayPortSwitchConfig(
                    port_number=port.port_number,
                    id_suffix="wan_connect_ipv4",
                    name_suffix="Internet Connected",
                    device_class=SwitchDeviceClass.SWITCH,
                    set_func=lambda p,
                    enable: omada_client.set_gateway_wan_port_connect_state(
                        p.port_number, enable, gateway, ipv6=False
                    ),
                    update_func=lambda p: p.wan_connected,
                ),
            )

            if port.wan_ipv6_enabled:
                yield OmadaGatewayPortSwitchEntity(
                    coordinator,
                    gateway,
                    GatewayPortSwitchConfig(
                        port_number=port.port_number,
                        id_suffix="wan_connect_ipv6",
                        name_suffix="Internet Connected (IPv6)",
                        device_class=SwitchDeviceClass.SWITCH,
                        set_func=lambda p,
                        enable: omada_client.set_gateway_wan_port_connect_state(
                            p.port_number, enable, gateway, ipv6=True
                        ),
                        update_func=lambda p: p.wan_connected,
                    ),
                )


def get_port_base_name(port: OmadaSwitchPortDetails) -> str:
    """Get display name for a switch port."""

    if port.name == f"Port{port.port}":
        return f"Port {port.port}"
    return f"Port {port.port} ({port.name})"


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

        self._attr_name = f"{get_port_base_name(self.port_details)} PoE"

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


@dataclass
class GatewayPortSwitchConfig:
    """Config for a toggle switch derived from a gateway."""

    port_number: int
    id_suffix: str
    name_suffix: str
    device_class: SwitchDeviceClass
    set_func: Callable[
        [OmadaGatewayPortStatus, bool], Awaitable[OmadaGatewayPortStatus]
    ]
    update_func: Callable[[OmadaGatewayPortStatus], bool]


class OmadaGatewayPortSwitchEntity(OmadaDeviceEntity[OmadaGateway], SwitchEntity):
    """Generic toggle switch on a Gateway entity."""

    _attr_available = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = POE_SWITCH_ICON
    _port_details: OmadaGatewayPortStatus | None = None

    def __init__(
        self,
        coordinator: OmadaGatewayCoordinator,
        device: OmadaGateway,
        config: GatewayPortSwitchConfig,
    ) -> None:
        """Initialize the toggle switch."""
        super().__init__(coordinator, device)
        self._config = config
        self._attr_unique_id = f"{device.mac}_{config.port_number}_{config.id_suffix}"
        self._attr_name = f"Port {config.port_number} {config.name_suffix}"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def _async_turn_on_off(self, enable: bool) -> None:
        if self._port_details is None:
            return
        self._port_details = await self._config.set_func(self._port_details, enable)
        # Refresh to make sure the requested changes stuck
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._async_turn_on_off(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._async_turn_on_off(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        gateway = self.coordinator.data[self.device.mac]

        port = next(
            p for p in gateway.port_status if p.port_number == self._config.port_number
        )
        if port:
            self._port_details = port
            self._attr_is_on = self._config.update_func(port)
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()
