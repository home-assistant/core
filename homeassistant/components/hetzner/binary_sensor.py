"""Binary sensor platform for the Hetzner Cloud integration."""

from __future__ import annotations

from hcloud.load_balancers.domain import LoadBalancerTarget

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HetznerConfigEntry, HetznerCoordinator
from .entity import HetznerEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HetznerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hetzner Cloud binary sensors."""
    coordinator = entry.runtime_data.coordinator

    entities: list[HetznerLoadBalancerTargetHealthSensor] = []
    for lb_id, lb in coordinator.data.items():
        for target in lb.data_model.targets or []:
            if (
                target.type == "server"
                and target.server is not None
                and target.server.id is not None
            ):
                server_id = target.server.id
                server_name = coordinator.server_names.get(server_id, str(server_id))
                entities.append(
                    HetznerLoadBalancerTargetHealthSensor(
                        coordinator=coordinator,
                        lb_id=lb_id,
                        target_type="server",
                        target_id=str(server_id),
                        target_name=server_name,
                    )
                )
            elif target.type == "ip" and target.ip is not None:
                ip_addr = target.ip.ip or "unknown"
                entities.append(
                    HetznerLoadBalancerTargetHealthSensor(
                        coordinator=coordinator,
                        lb_id=lb_id,
                        target_type="ip",
                        target_id=ip_addr,
                        target_name=ip_addr,
                    )
                )

    async_add_entities(entities)


class HetznerLoadBalancerTargetHealthSensor(HetznerEntity, BinarySensorEntity):
    """Binary sensor for Hetzner Cloud load balancer target health."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "target_health"

    def __init__(
        self,
        coordinator: HetznerCoordinator,
        lb_id: int,
        target_type: str,
        target_id: str,
        target_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, lb_id)
        self._target_type = target_type
        self._target_id = target_id
        self._attr_unique_id = f"{lb_id}_target_{target_type}_{target_id}"
        self._attr_translation_placeholders = {"target_name": target_name}

    @property
    def is_on(self) -> bool | None:
        """Return true if the target is healthy."""
        lb = self.coordinator.data.get(self.lb_id)
        if lb is None:
            return None

        for target in lb.data_model.targets or []:
            if self._matches_target(target):
                if not target.health_status:
                    return None
                return all(hs.status == "healthy" for hs in target.health_status)

        return None

    def _matches_target(self, target: LoadBalancerTarget) -> bool:
        """Check if a target matches this sensor."""
        if self._target_type == "server" and target.type == "server":
            return (
                target.server is not None and str(target.server.id) == self._target_id
            )
        if self._target_type == "ip" and target.type == "ip":
            return target.ip is not None and target.ip.ip == self._target_id
        return False
