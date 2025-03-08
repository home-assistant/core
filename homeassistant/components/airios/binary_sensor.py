"""Binary sensor platform for the Airios integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast, final

from pyairios import ProductId
from pyairios.constants import BatteryStatus, FaultStatus
from pyairios.data_model import AiriosNodeData
from pyairios.exceptions import AiriosException
from pyairios.vmd_02rps78 import VMD02RPS78

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_SLAVE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VMDEntityFeature
from .coordinator import AiriosDataUpdateCoordinator
from .entity import AiriosEntity
from .services import SERVICE_FILTER_RESET

_LOGGER = logging.getLogger(__name__)


def rf_comm_status_value_fn(v: int) -> bool | None:
    """Convert timedelta to sensor's value."""
    if v == 0:
        return True
    if v == 1:
        return False
    return None


def _battery_status_value_fn(v: BatteryStatus) -> bool | None:
    if v.available:
        return v.low != 0
    return None


def _fault_status_value_fn(v: FaultStatus) -> bool | None:
    if v.available:
        return v.fault
    return None


@dataclass(frozen=True, kw_only=True)
class AiriosBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Airios binary sensor description."""

    value_fn: Callable[[Any], bool | None] | None = None
    supported_features: VMDEntityFeature | None = None


class AiriosBinarySensorEntity(AiriosEntity, BinarySensorEntity):
    """Airios binary sensor."""

    entity_description: AiriosBinarySensorEntityDescription

    def __init__(
        self,
        description: AiriosBinarySensorEntityDescription,
        coordinator: AiriosDataUpdateCoordinator,
        node: AiriosNodeData,
        via_config_entry: ConfigEntry | None,
        subentry: ConfigSubentry | None,
    ) -> None:
        """Initialize the binary sensor entity."""

        super().__init__(description.key, coordinator, node, via_config_entry, subentry)
        self.entity_description = description
        self._attr_supported_features = description.supported_features

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update data from the coordinator."""
        _LOGGER.debug(
            "Handle update for node %s binary sensor %s",
            f"{self.rf_address}",
            self.entity_description.key,
        )
        try:
            device = self.coordinator.data.nodes[self.slave_id]
            result = device[self.entity_description.key]
            _LOGGER.debug(
                "Node %s, binary sensor %s, result %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                result,
            )
            if result is not None and result.value is not None:
                if self.entity_description.value_fn:
                    self._attr_is_on = self.entity_description.value_fn(result.value)
                else:
                    self._attr_is_on = result.value
                self._attr_available = self._attr_is_on is not None
                if result.status is not None:
                    self.set_extra_state_attributes_internal(result.status)
        except (TypeError, ValueError) as ex:
            _LOGGER.error(
                "Failed to update binary node %s sensor %s: %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                ex,
            )
            self._attr_is_on = None
            self._attr_available = False
        finally:
            self.async_write_ha_state()

    @final
    async def async_filter_reset(self) -> bool:
        """Reset the filter dirty flag."""
        node = cast(VMD02RPS78, await self.api().node(self.slave_id))
        _LOGGER.debug("Reset filter dirty flag for node %s", str(node))
        try:
            if not await node.filter_reset():
                raise HomeAssistantError("Failed to reset filter dirty flag")
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to reset filter dirty flag: {ex}") from ex
        return True


NODE_BINARY_SENSOR_ENTITIES: tuple[AiriosBinarySensorEntityDescription, ...] = (
    AiriosBinarySensorEntityDescription(
        key="fault_status",
        translation_key="fault_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_fault_status_value_fn,
    ),
    AiriosBinarySensorEntityDescription(
        key="rf_comm_status",
        translation_key="rf_comm_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=rf_comm_status_value_fn,
    ),
)

VMD_BINARY_SENSOR_ENTITIES: tuple[AiriosBinarySensorEntityDescription, ...] = (
    AiriosBinarySensorEntityDescription(
        key="filter_dirty",
        translation_key="filter_dirty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        supported_features=VMDEntityFeature.FILTER_RESET,
    ),
    AiriosBinarySensorEntityDescription(
        key="defrost",
        translation_key="defrost",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)

VMN_BINARY_SENSOR_ENTITIES: tuple[AiriosBinarySensorEntityDescription, ...] = (
    AiriosBinarySensorEntityDescription(
        key="battery_status",
        translation_key="battery_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_battery_status_value_fn,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""

    coordinator: AiriosDataUpdateCoordinator = entry.runtime_data

    for slave_id, node in coordinator.data.nodes.items():
        # Find matching subentry
        subentry_id = None
        subentry = None
        via_config_entry = None
        for se_id, se in entry.subentries.items():
            if se.data[CONF_SLAVE] == slave_id:
                subentry_id = se_id
                subentry = se
                via_config_entry = entry

        entities: list[AiriosBinarySensorEntity] = [
            AiriosBinarySensorEntity(
                description,
                coordinator,
                node,
                via_config_entry,
                subentry,
            )
            for description in NODE_BINARY_SENSOR_ENTITIES
        ]
        result = node["product_id"]
        if result is None or result.value is None:
            raise ConfigEntryNotReady("Failed to fetch product id from node")
        if result.value == ProductId.VMD_02RPS78:
            entities.extend(
                [
                    AiriosBinarySensorEntity(
                        description,
                        coordinator,
                        node,
                        via_config_entry,
                        subentry,
                    )
                    for description in VMD_BINARY_SENSOR_ENTITIES
                ]
            )
        if result.value == ProductId.VMN_05LM02:
            entities.extend(
                [
                    AiriosBinarySensorEntity(
                        description,
                        coordinator,
                        node,
                        via_config_entry,
                        subentry,
                    )
                    for description in VMN_BINARY_SENSOR_ENTITIES
                ]
            )
        async_add_entities(entities, config_subentry_id=subentry_id)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_FILTER_RESET,
        None,
        "async_filter_reset",
        required_features=[VMDEntityFeature.FILTER_RESET],
    )
