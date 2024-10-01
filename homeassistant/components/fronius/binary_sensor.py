"""Binary sensors for Fronius devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import FroniusEntityDescription, _FroniusEntity

if TYPE_CHECKING:
    from . import FroniusConfigEntry
    from .coordinator import FroniusPowerFlowUpdateCoordinator


@dataclass(frozen=True)
class FroniusBinarySensorEntityDescription(
    FroniusEntityDescription, BinarySensorEntityDescription
):
    """Describes Fronius binary_sensor entity."""

    default_value: bool | None = None
    response_key: str | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fronius binary_sensor entities based on a config entry."""
    solar_net = config_entry.runtime_data

    if solar_net.power_flow_coordinator is not None:
        solar_net.power_flow_coordinator.add_binary_entities_for_seen_keys(
            async_add_entities, PowerFlowBinarySensor
        )


POWER_FLOW_BINARY_ENTITY_DESCRIPTIONS: list[FroniusBinarySensorEntityDescription] = [
    FroniusBinarySensorEntityDescription(
        name="Backup mode",
        key="backup_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FroniusBinarySensorEntityDescription(
        name="Battery standby",
        key="battery_standby",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


class _FroniusBinarySensorEntity(_FroniusEntity, BinarySensorEntity):
    """Defines a Fronius binary_sensor entity."""

    entity_description: FroniusBinarySensorEntityDescription

    def _get_entity_value(self) -> bool | None:
        """Extract entity value from coordinator. Raises KeyError if not included in latest update."""
        new_value = self.coordinator.data[self.solar_net_id][self.response_key]["value"]
        if new_value is None:
            return self.entity_description.default_value
        return bool(new_value)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._attr_is_on = self._get_entity_value()
        except KeyError:
            # sets state to `None` if no default_value is defined in entity description
            # KeyError: raised when omitted in response - eg. at night when no production
            self._attr_native_value = self.entity_description.default_value
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
