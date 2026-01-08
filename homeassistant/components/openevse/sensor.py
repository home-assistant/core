"""Support for monitoring an OpenEVSE Charger."""

from __future__ import annotations

import logging

from openevsehttp.__main__ import OpenEVSE
import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import ConfigEntry
from .const import DOMAIN, INTEGRATION_TITLE

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="status",
        translation_key="status",
    ),
    SensorEntityDescription(
        key="charge_time",
        translation_key="charge_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ambient_temp",
        translation_key="ambient_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ir_temp",
        translation_key="ir_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="rtc_temp",
        translation_key="rtc_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="usage_session",
        translation_key="usage_session",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="usage_total",
        translation_key="usage_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
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
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    async_add_entities(
        (
            OpenEVSESensor(
                config_entry,
                config_entry.runtime_data,
                description,
            )
            for description in SENSOR_TYPES
        ),
        True,
    )


class OpenEVSESensor(SensorEntity):
    """Implementation of an OpenEVSE sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        charger: OpenEVSE,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.charger = charger

        if config_entry.unique_id:
            self._attr_unique_id = f"{config_entry.unique_id}_{description.key}"

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, config_entry.unique_id)},
                name="OpenEVSE",
                manufacturer="OpenEVSE",
            )

    async def async_update(self) -> None:
        """Get the monitored data from the charger."""
        try:
            await self.charger.update()
        except TimeoutError:
            _LOGGER.warning("Could not update status for %s", self.name)
            return

        sensor_type = self.entity_description.key
        if sensor_type == "status":
            self._attr_native_value = self.charger.status
        elif sensor_type == "charge_time":
            self._attr_native_value = self.charger.charge_time_elapsed / 60
        elif sensor_type == "ambient_temp":
            self._attr_native_value = self.charger.ambient_temperature
        elif sensor_type == "ir_temp":
            self._attr_native_value = self.charger.ir_temperature
        elif sensor_type == "rtc_temp":
            self._attr_native_value = self.charger.rtc_temperature
        elif sensor_type == "usage_session":
            self._attr_native_value = float(self.charger.usage_session) / 1000
        elif sensor_type == "usage_total":
            self._attr_native_value = float(self.charger.usage_total) / 1000
        else:
            self._attr_native_value = "Unknown"
