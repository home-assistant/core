"""Support for Fronius binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from fronius_solarapi import PowerFlow

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FroniusPowerFlowUpdateCoordinator
from .entity import (
    FroniusEntity,
    FroniusEntityDescription,
    async_add_entities_for_seen_keys,
)

if TYPE_CHECKING:
    from . import FroniusConfigEntry


PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class FroniusBinarySensorEntityDescription[_DataT](
    FroniusEntityDescription[_DataT], BinarySensorEntityDescription
):
    """Describes Fronius binary sensor entity."""

    value_fn: Callable[[_DataT], bool | None]


POWER_FLOW_BINARY_SENSOR_DESCRIPTIONS: list[
    FroniusBinarySensorEntityDescription[PowerFlow]
] = [
    FroniusBinarySensorEntityDescription(
        key="backup_mode",
        value_fn=lambda data: data.site.backup_mode,
    ),
    FroniusBinarySensorEntityDescription(
        key="battery_standby",
        value_fn=lambda data: data.site.battery_standby,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fronius binary sensor entities based on a config entry."""
    for coordinator in config_entry.runtime_data.coordinators:
        if isinstance(coordinator, FroniusPowerFlowUpdateCoordinator):
            async_add_entities_for_seen_keys(
                coordinator,
                POWER_FLOW_BINARY_SENSOR_DESCRIPTIONS,
                PowerFlowBinarySensor,
                async_add_entities,
            )


class PowerFlowBinarySensor(FroniusEntity, BinarySensorEntity):
    """Defines a Fronius power flow binary sensor entity."""

    entity_description: FroniusBinarySensorEntityDescription[PowerFlow]

    def __init__(
        self,
        coordinator: FroniusPowerFlowUpdateCoordinator,
        description: FroniusBinarySensorEntityDescription[PowerFlow],
        solar_net_id: str,
    ) -> None:
        """Set up an individual Fronius power flow binary sensor."""
        super().__init__(coordinator, description, solar_net_id)
        self._attr_is_on = self._value()
        # SolarNet device is already created in FroniusSolarNet._create_solar_net_device
        self._attr_device_info = coordinator.solar_net.system_device_info
        self._attr_unique_id = (
            f"{coordinator.solar_net.solar_net_device_id}-power_flow-{description.key}"
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # `None` when omitted in the response, e.g. when backup power is
        # deactivated after the entity was created
        self._attr_is_on = self._value()
        self.async_write_ha_state()
