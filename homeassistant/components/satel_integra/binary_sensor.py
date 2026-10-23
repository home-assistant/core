"""Support for Satel Integra zone states- represented as binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from satel_integra import SatelRtcAndStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import (
    SatelConfigEntry,
    SatelIntegraBaseCoordinator,
    SatelIntegraSystemStatusCoordinator,
)
from .entity import SatelIntegraEntity, SatelIntegraPanelEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SatelIntegraSystemStatusBinarySensorEntityDescription(
    BinarySensorEntityDescription
):
    """Describes a Satel Integra system status binary sensor."""

    is_on_fn: Callable[[SatelRtcAndStatus | None], bool | None]


SYSTEM_STATUS_BINARY_SENSORS = (
    SatelIntegraSystemStatusBinarySensorEntityDescription(
        key="system_trouble",
        translation_key="system_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda status: status.troubles if status is not None else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra binary sensor devices."""

    runtime_data = config_entry.runtime_data

    async_add_entities(
        [
            SatelIntegraSystemStatusBinarySensor(
                runtime_data.coordinator_system_status,
                config_entry.entry_id,
                description,
            )
            for description in SYSTEM_STATUS_BINARY_SENSORS
        ]
    )

    for subentry in config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE):
        zone_num: int = subentry.data[CONF_ZONE_NUMBER]
        zone_type: BinarySensorDeviceClass = subentry.data[CONF_ZONE_TYPE]

        async_add_entities(
            [
                SatelIntegraBinarySensor(
                    runtime_data.coordinator_zones,
                    config_entry.entry_id,
                    subentry,
                    zone_num,
                    zone_type,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )

    for subentry in config_entry.get_subentries_of_type(SUBENTRY_TYPE_OUTPUT):
        output_num: int = subentry.data[CONF_OUTPUT_NUMBER]
        output_type: BinarySensorDeviceClass = subentry.data[CONF_ZONE_TYPE]

        async_add_entities(
            [
                SatelIntegraBinarySensor(
                    runtime_data.coordinator_outputs,
                    config_entry.entry_id,
                    subentry,
                    output_num,
                    output_type,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraBinarySensor[_CoordinatorT: SatelIntegraBaseCoordinator](
    SatelIntegraEntity[_CoordinatorT], BinarySensorEntity
):
    """Base binary sensor for Satel Integra."""

    _attr_name = None

    def __init__(
        self,
        coordinator: _CoordinatorT,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize the binary_sensor."""
        super().__init__(
            coordinator,
            config_entry_id,
            subentry,
            device_number,
        )

        self._attr_device_class = device_class

        self._attr_is_on = self._get_state_from_coordinator()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._get_state_from_coordinator()
        self.async_write_ha_state()

    def _get_state_from_coordinator(self) -> bool | None:
        """Method to get binary sensor state from coordinator data."""
        return self.coordinator.data.get(self._device_number)


class SatelIntegraSystemStatusBinarySensor(
    SatelIntegraPanelEntity[SatelIntegraSystemStatusCoordinator], BinarySensorEntity
):
    """Representation of a Satel Integra system status binary sensor."""

    entity_description: SatelIntegraSystemStatusBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SatelIntegraSystemStatusCoordinator,
        config_entry_id: str,
        description: SatelIntegraSystemStatusBinarySensorEntityDescription,
    ) -> None:
        """Initialize the system status binary sensor."""
        super().__init__(coordinator, config_entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry_id}_{description.key}"
        self._attr_is_on = self._get_state_from_coordinator()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated system status data."""
        self._attr_is_on = self._get_state_from_coordinator()
        self.async_write_ha_state()

    def _get_state_from_coordinator(self) -> bool | None:
        """Return the state described by the entity description."""
        return self.entity_description.is_on_fn(self.coordinator.data)
