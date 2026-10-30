"""Support for Satel Integra zone states- represented as binary sensors."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import override

from satel_integra import SatelSystemTroubles, SatelTrouble, SatelTroubleType

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
    SatelIntegraSystemStatusData,
)
from .entity import SatelIntegraBaseEntity, SatelIntegraEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SatelIntegraSystemStatusBinarySensorEntityDescription(
    BinarySensorEntityDescription
):
    """Describes a Satel Integra system status binary sensor."""

    is_on_fn: Callable[[SatelIntegraSystemStatusData], bool | None]


def _has_system_trouble(
    troubles: SatelSystemTroubles | None, trouble: SatelTrouble
) -> bool | None:
    """Return whether a specific system trouble is active."""
    if troubles is None:
        return None
    return trouble in troubles.troubles


def _trouble_sensor_description(
    key: str,
    trouble_type: SatelTroubleType,
    *,
    source_id: int | None = None,
    translation_key: str | None = None,
    translation_placeholders: Mapping[str, str] | None = None,
) -> SatelIntegraSystemStatusBinarySensorEntityDescription:
    """Return an entity description for a specific system trouble."""
    trouble = SatelTrouble(trouble_type, source_id=source_id)
    return SatelIntegraSystemStatusBinarySensorEntityDescription(
        key=key,
        translation_key=translation_key or key,
        translation_placeholders=translation_placeholders,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda data: _has_system_trouble(data.troubles, trouble),
    )


SYSTEM_STATUS_BINARY_SENSORS = (
    SatelIntegraSystemStatusBinarySensorEntityDescription(
        key="service_mode",
        translation_key="service_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (
            data.status.service_mode if data.status is not None else None
        ),
    ),
    SatelIntegraSystemStatusBinarySensorEntityDescription(
        key="system_trouble",
        translation_key="system_trouble",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data.status.troubles if data.status is not None else None,
    ),
    _trouble_sensor_description("panel_ac_trouble", SatelTroubleType.PANEL_AC),
    _trouble_sensor_description(
        "panel_battery_trouble", SatelTroubleType.PANEL_BATTERY
    ),
    _trouble_sensor_description(
        "output_1_trouble",
        SatelTroubleType.OUTPUT,
        source_id=1,
        translation_key="output_trouble",
        translation_placeholders={"number": "1"},
    ),
    _trouble_sensor_description(
        "output_2_trouble",
        SatelTroubleType.OUTPUT,
        source_id=2,
        translation_key="output_trouble",
        translation_placeholders={"number": "2"},
    ),
    _trouble_sensor_description(
        "output_3_trouble",
        SatelTroubleType.OUTPUT,
        source_id=3,
        translation_key="output_trouble",
        translation_placeholders={"number": "3"},
    ),
    _trouble_sensor_description(
        "output_4_trouble",
        SatelTroubleType.OUTPUT,
        source_id=4,
        translation_key="output_trouble",
        translation_placeholders={"number": "4"},
    ),
    _trouble_sensor_description(
        "keypad_power_supply_trouble", SatelTroubleType.KEYPAD_POWER_SUPPLY
    ),
    _trouble_sensor_description(
        "expander_power_supply_trouble", SatelTroubleType.EXPANDER_POWER_SUPPLY
    ),
    _trouble_sensor_description("dt1_trouble", SatelTroubleType.DT1),
    _trouble_sensor_description("dt2_trouble", SatelTroubleType.DT2),
    _trouble_sensor_description("dtm_trouble", SatelTroubleType.DTM),
    _trouble_sensor_description("rtc_trouble", SatelTroubleType.RTC),
    _trouble_sensor_description(
        "external_device_dtr_trouble", SatelTroubleType.EXTERNAL_DEVICE_DTR
    ),
    _trouble_sensor_description(
        "panel_battery_missing_trouble", SatelTroubleType.PANEL_BATTERY_MISSING
    ),
    _trouble_sensor_description(
        "external_modem_initialization_trouble",
        SatelTroubleType.EXTERNAL_MODEM_INITIALIZATION,
    ),
    _trouble_sensor_description(
        "external_modem_command_trouble", SatelTroubleType.EXTERNAL_MODEM_COMMAND
    ),
    _trouble_sensor_description(
        "telephone_line_voltage_or_auxiliary_processor_trouble",
        SatelTroubleType.TELEPHONE_LINE_VOLTAGE_OR_AUXILIARY_PROCESSOR,
    ),
    _trouble_sensor_description(
        "telephone_line_bad_signal_trouble",
        SatelTroubleType.TELEPHONE_LINE_BAD_SIGNAL,
    ),
    _trouble_sensor_description(
        "telephone_line_no_signal_trouble",
        SatelTroubleType.TELEPHONE_LINE_NO_SIGNAL,
    ),
    _trouble_sensor_description(
        "monitoring_station_1_trouble",
        SatelTroubleType.MONITORING_STATION,
        source_id=1,
        translation_key="monitoring_station_trouble",
        translation_placeholders={"number": "1"},
    ),
    _trouble_sensor_description(
        "monitoring_station_2_trouble",
        SatelTroubleType.MONITORING_STATION,
        source_id=2,
        translation_key="monitoring_station_trouble",
        translation_placeholders={"number": "2"},
    ),
    _trouble_sensor_description(
        "eeprom_or_rtc_access_trouble", SatelTroubleType.EEPROM_OR_RTC_ACCESS
    ),
    _trouble_sensor_description("ram_trouble", SatelTroubleType.RAM),
    _trouble_sensor_description(
        "panel_restart_memory_trouble", SatelTroubleType.PANEL_RESTART_MEMORY
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
    SatelIntegraBaseEntity[SatelIntegraSystemStatusCoordinator], BinarySensorEntity
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
