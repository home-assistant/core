"""Support for TPLink Omada device toggle options."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from tplink_omada_client.definitions import PoEMode
from tplink_omada_client.devices import OmadaSwitch, OmadaSwitchPortDetails
from tplink_omada_client.omadasiteclient import OmadaSiteClient, SwitchPortOverrides

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OmadaCoordinator
from .entity import OmadaSwitchDeviceEntity

POE_SWITCH_ICON = "mdi:ethernet"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    omada_client: OmadaSiteClient = hass.data[DOMAIN][config_entry.entry_id]

    # Naming fun. Omada switches, as in the network hardware
    network_switches = await omada_client.get_switches()

    entities: list = []
    for switch in [
        ns for ns in network_switches if ns.device_capabilities.supports_poe
    ]:

        def make_update_func(
            network_switch: OmadaSwitch,
        ) -> Callable[[OmadaSiteClient], Awaitable[dict[str, OmadaSwitchPortDetails]]]:
            async def update_func(
                client: OmadaSiteClient,
            ) -> dict[str, OmadaSwitchPortDetails]:
                ports = await client.get_switch_ports(network_switch)
                return {p.port_id: p for p in ports}

            return update_func

        coordinator = OmadaCoordinator[OmadaSwitchPortDetails](
            hass, omada_client, make_update_func(switch)
        )

        await coordinator.async_config_entry_first_refresh()

        for idx, port_id in enumerate(coordinator.data):
            if idx < switch.device_capabilities.poe_ports:
                entities.append(
                    OmadaNetworkSwitchPortPoEControl(
                        coordinator, switch, omada_client, port_id
                    )
                )

    async_add_entities(entities)


def get_port_base_name(port: OmadaSwitchPortDetails) -> str:
    """Get display name for a switch port."""

    if port.name == f"Port{port.port}":
        return f"Port {port.port}"
    return f"Port {port.port} ({port.name})"


class OmadaNetworkSwitchPortPoEControl(OmadaSwitchDeviceEntity, SwitchEntity):
    """Representation of a PoE control toggle on a single network port on a switch."""

    def __init__(
        self,
        coordinator: OmadaCoordinator[OmadaSwitchPortDetails],
        device: OmadaSwitch,
        omada_client: OmadaSiteClient,
        port_id: str,
    ) -> None:
        """Initialize the PoE switch."""
        super().__init__(coordinator, device)
        self.port_id = port_id
        self.port_details = self.coordinator.data[port_id]
        self.omada_client = omada_client
        self._attr_unique_id = f"{device.mac}_{port_id}_poe"

        port_name = f"{get_port_base_name(self.port_details)} PoE"

        self.entity_description = SwitchEntityDescription(
            f"PoE Enabled Port {self.port_details.port}",
            name=port_name,
            has_entity_name=True,
            entity_category=EntityCategory.CONFIG,
            icon=POE_SWITCH_ICON,
        )
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
        if self.hass:
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.port_details = self.coordinator.data[self.port_id]
        self._refresh_state()
