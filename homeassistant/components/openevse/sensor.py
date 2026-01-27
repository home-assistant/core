"""Support for monitoring an OpenEVSE Charger."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from openevsehttp.__main__ import OpenEVSE
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_SERIAL_NUMBER,
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_TITLE
from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenEVSESensorDescription(SensorEntityDescription):
    """Describes an OpenEVSE sensor entity."""

    value_fn: Callable[[OpenEVSE], str | float | None]


SENSOR_TYPES: tuple[OpenEVSESensorDescription, ...] = (
    OpenEVSESensorDescription(
        key="status",
        translation_key="status",
        value_fn=lambda ev: ev.status,
    ),
    OpenEVSESensorDescription(
        key="charge_time",
        translation_key="charge_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.charge_time_elapsed,
    ),
    OpenEVSESensorDescription(
        key="ambient_temp",
        translation_key="ambient_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.ambient_temperature,
    ),
    OpenEVSESensorDescription(
        key="ir_temp",
        translation_key="ir_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.ir_temperature,
        entity_registry_enabled_default=False,
    ),
    OpenEVSESensorDescription(
        key="rtc_temp",
        translation_key="rtc_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ev: ev.rtc_temperature,
        entity_registry_enabled_default=False,
    ),
    OpenEVSESensorDescription(
        key="usage_session",
        translation_key="usage_session",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda ev: ev.usage_session,
    ),
    OpenEVSESensorDescription(
        key="usage_total",
        translation_key="usage_total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda ev: ev.usage_total,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES, default=["status"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the openevse platform."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE sensors based on config entry."""
    coordinator = entry.runtime_data
    identifier = entry.unique_id or entry.entry_id
    async_add_entities(
        OpenEVSESensor(coordinator, description, identifier, entry.unique_id)
        for description in SENSOR_TYPES
    )


class OpenEVSESensor(CoordinatorEntity[OpenEVSEDataUpdateCoordinator], SensorEntity):
    """Implementation of an OpenEVSE sensor."""

    _attr_has_entity_name = True
    entity_description: OpenEVSESensorDescription

    def __init__(
        self,
        coordinator: OpenEVSEDataUpdateCoordinator,
        description: OpenEVSESensorDescription,
        identifier: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="OpenEVSE",
        )
        if unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, unique_id)
            }
            self._attr_device_info[ATTR_SERIAL_NUMBER] = unique_id

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.charger)
