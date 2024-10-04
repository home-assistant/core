"""Binary sensors for Fronius devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FroniusEntity, FroniusEntityDescription

if TYPE_CHECKING:
    from . import FroniusConfigEntry
    from .coordinator import FroniusPowerFlowUpdateCoordinator


@dataclass(frozen=True)
class FroniusBinarySensorEntityDescription(
    FroniusEntityDescription, BinarySensorEntityDescription
):
    """Describes Fronius binary_sensor entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fronius binary_sensor entities based on a config entry."""
    solar_net = config_entry.runtime_data

    if solar_net.power_flow_coordinator is not None:
        solar_net.power_flow_coordinator.add_entities_for_seen_keys(
            async_add_entities,
            Platform.BINARY_SENSOR,
            PowerFlowBinarySensor,
        )


POWER_FLOW_BINARY_ENTITY_DESCRIPTIONS: list[FroniusEntityDescription] = [
    FroniusBinarySensorEntityDescription(
        name="Backup mode",
        key="backup_mode",
    ),
    FroniusBinarySensorEntityDescription(
        name="Battery standby",
        key="battery_standby",
    ),
]


class _FroniusBinarySensorEntity(FroniusEntity, BinarySensorEntity):
    """Defines a Fronius binary_sensor entity."""

    entity_description: FroniusBinarySensorEntityDescription

    def _get_entity_value(self) -> bool | None:
        """Extract entity value from coordinator. Raises KeyError if not included in latest update."""
        return bool(
            self.coordinator.data[self.solar_net_id][self.response_key]["value"]
        )

    def _set_entity_value(self) -> None:
        """binary_sensor requires a boolean value in _attr_is_on."""
        self._attr_is_on = self._get_entity_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._get_entity_value()
        self.async_write_ha_state()


class PowerFlowBinarySensor(_FroniusBinarySensorEntity):
    """Defines a Fronius power flow binary_sensor entity."""

    def __init__(
        self,
        coordinator: FroniusPowerFlowUpdateCoordinator,
        description: FroniusBinarySensorEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius power flow binary_sensor."""
        super().__init__(coordinator, description, solar_net_id)
        # SolarNet device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_unique_id = (
            f"{coordinator.solar_net.solar_net_device_id}-power_flow-{description.key}"
        )
