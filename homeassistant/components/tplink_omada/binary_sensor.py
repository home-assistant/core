"""Support for TPLink Omada binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tplink_omada_client.definitions import GatewayPortMode, LinkStatus, PoEMode
from tplink_omada_client.devices import (
    OmadaDevice,
    OmadaGatewayPortConfig,
    OmadaGatewayPortStatus,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OmadaConfigEntry
from .controller import OmadaGatewayCoordinator
from .entity import OmadaDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    controller = config_entry.runtime_data

    gateway_coordinator = controller.gateway_coordinator
    if not gateway_coordinator:
        return

    entities: list[OmadaDeviceEntity] = []
    for gateway in gateway_coordinator.data.values():
        entities.extend(
            OmadaGatewayPortBinarySensor(
                gateway_coordinator, gateway, p.port_number, desc
            )
            for p in gateway.port_configs
            for desc in GATEWAY_PORT_SENSORS
            if desc.exists_func(p)
        )

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class GatewayPortBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity description for a binary status derived from a gateway port."""

    exists_func: Callable[[OmadaGatewayPortConfig], bool] = lambda _: True
    update_func: Callable[[OmadaGatewayPortStatus], bool]


GATEWAY_PORT_SENSORS: list[GatewayPortBinarySensorEntityDescription] = [
    GatewayPortBinarySensorEntityDescription(
        key="wan_link",
        translation_key="wan_link",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        exists_func=lambda p: p.port_status.mode == GatewayPortMode.WAN,
        update_func=lambda p: p.wan_connected,
    ),
    GatewayPortBinarySensorEntityDescription(
        key="online_detection",
        translation_key="online_detection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        exists_func=lambda p: p.port_status.mode == GatewayPortMode.WAN,
        update_func=lambda p: p.online_detection,
    ),
    GatewayPortBinarySensorEntityDescription(
        key="lan_status",
        translation_key="lan_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        exists_func=lambda p: p.port_status.mode == GatewayPortMode.LAN,
        update_func=lambda p: p.link_status == LinkStatus.LINK_UP,
    ),
    GatewayPortBinarySensorEntityDescription(
        key="poe_delivery",
        translation_key="poe_delivery",
        device_class=BinarySensorDeviceClass.POWER,
        exists_func=lambda p: (
            p.port_status.mode == GatewayPortMode.LAN and p.poe_mode == PoEMode.ENABLED
        ),
        update_func=lambda p: p.poe_active,
    ),
]


class OmadaGatewayPortBinarySensor(
    OmadaDeviceEntity[OmadaGatewayCoordinator], BinarySensorEntity
):
    """Binary status of a property on an internet gateway."""

    entity_description: GatewayPortBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OmadaGatewayCoordinator,
        device: OmadaDevice,
        port_number: int,
        entity_description: GatewayPortBinarySensorEntityDescription,
    ) -> None:
        """Initialize the gateway port binary sensor."""
        super().__init__(coordinator, device)
        self.entity_description = entity_description
        self._port_number = port_number
        self._attr_unique_id = f"{device.mac}_{port_number}_{entity_description.key}"
        self._attr_translation_placeholders = {"port_name": f"{port_number}"}

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._do_update()

    def _do_update(self) -> None:
        gateway = self.coordinator.data[self.device.mac]

        port = next(
            p for p in gateway.port_status if p.port_number == self._port_number
        )
        if port:
            self._attr_is_on = self.entity_description.update_func(port)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._do_update()
        self.async_write_ha_state()
