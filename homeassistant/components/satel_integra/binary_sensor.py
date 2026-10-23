"""Support for Satel Integra zone states- represented as binary sensors."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra binary sensor devices."""

    runtime_data = config_entry.runtime_data

    async_add_entities(
        [
            SatelIntegraSystemTroubleBinarySensor(
                runtime_data.coordinator_system_status,
                config_entry.entry_id,
            )
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


class SatelIntegraSystemTroubleBinarySensor(
    SatelIntegraPanelEntity[SatelIntegraSystemStatusCoordinator], BinarySensorEntity
):
    """Representation of the overall Satel Integra system trouble status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "system_trouble"

    def __init__(
        self,
        coordinator: SatelIntegraSystemStatusCoordinator,
        config_entry_id: str,
    ) -> None:
        """Initialize the system trouble sensor."""
        super().__init__(coordinator, config_entry_id)
        self._attr_unique_id = f"{config_entry_id}_system_trouble"
        self._attr_is_on = self._get_state_from_coordinator()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated system status data."""
        self._attr_is_on = self._get_state_from_coordinator()
        self.async_write_ha_state()

    def _get_state_from_coordinator(self) -> bool | None:
        """Return whether the panel reports an active system trouble."""
        if (system_status := self.coordinator.data) is None:
            return None
        return system_status.troubles
