"""Support for TPLink Omada binary sensors."""
from __future__ import annotations

from collections.abc import Callable, Generator

from attr import dataclass
from tplink_omada_client.definitions import GatewayPortMode, LinkStatus
from tplink_omada_client.devices import OmadaDevice, OmadaGateway, OmadaGatewayPort

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import OmadaGatewayCoordinator, OmadaSiteController
from .entity import OmadaDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    controller: OmadaSiteController = hass.data[DOMAIN][config_entry.entry_id]
    omada_client = controller.omada_client

    gateway_coordinator = await controller.get_gateway_coordinator()
    if not gateway_coordinator:
        return

    gateway = await omada_client.get_gateway(gateway_coordinator.mac)

    async_add_entities(
        get_gateway_port_status_sensors(gateway, hass, gateway_coordinator)
    )

    await gateway_coordinator.async_request_refresh()


def get_gateway_port_status_sensors(
    gateway: OmadaGateway, hass: HomeAssistant, coordinator: OmadaGatewayCoordinator
) -> Generator[BinarySensorEntity, None, None]:
    """Generate binary sensors for gateway ports."""
    for port in gateway.port_status:
        if port.mode == GatewayPortMode.WAN:
            yield OmadaGatewayPortBinarySensor(
                coordinator,
                gateway,
                GatewayPortBinarySensorConfig(
                    port_number=port.port_number,
                    id_suffix="wan_link",
                    name_suffix="Internet Link",
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    update_func=lambda p: p.wan_connected,
                ),
            )
        if port.mode == GatewayPortMode.LAN:
            yield OmadaGatewayPortBinarySensor(
                coordinator,
                gateway,
                GatewayPortBinarySensorConfig(
                    port_number=port.port_number,
                    id_suffix="lan_status",
                    name_suffix="LAN Status",
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    update_func=lambda p: p.link_status == LinkStatus.LINK_UP,
                ),
            )


@dataclass
class GatewayPortBinarySensorConfig:
    """Config for a binary status derived from a gateway port."""

    port_number: int
    id_suffix: str
    name_suffix: str
    device_class: BinarySensorDeviceClass
    update_func: Callable[[OmadaGatewayPort], bool]


class OmadaGatewayPortBinarySensor(OmadaDeviceEntity[OmadaGateway], BinarySensorEntity):
    """Binary status of a property on an internet gateway."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OmadaGatewayCoordinator,
        device: OmadaDevice,
        config: GatewayPortBinarySensorConfig,
    ) -> None:
        """Initialize the gateway port binary sensor."""
        super().__init__(coordinator, device)
        self._config = config
        self._attr_unique_id = f"{device.mac}_{config.port_number}_{config.id_suffix}"
        self._attr_device_class = config.device_class

        self._attr_name = f"Port {config.port_number} {config.name_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        gateway = self.coordinator.data[self.device.mac]

        port = next(
            p for p in gateway.port_status if p.port_number == self._config.port_number
        )
        if port:
            self._attr_is_on = self._config.update_func(port)
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()
