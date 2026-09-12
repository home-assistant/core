"""SAJ solar inverter interface."""

from typing import override

import pysaj
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONNECTION_TYPES, DOMAIN, INTEGRATION_TITLE
from .coordinator import SAJConfigEntry, SAJDataUpdateCoordinator

SAJ_UNIT_MAPPINGS = {
    "": None,
    "h": UnitOfTime.HOURS,
    "kg": UnitOfMass.KILOGRAMS,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "W": UnitOfPower.WATT,
    "°C": UnitOfTemperature.CELSIUS,
}

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=CONNECTION_TYPES[0]): vol.In(CONNECTION_TYPES),
        vol.Inclusive(CONF_USERNAME, "credentials"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "credentials"): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SAJConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SAJ sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        SAJsensor(coordinator, entry.unique_id, sensor)
        for sensor in coordinator.sensor_def
        if sensor.enabled
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Migrate YAML sensor platform configuration to a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=dict(config),
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        reason = result.get("reason", "unknown")
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


class SAJsensor(CoordinatorEntity[SAJDataUpdateCoordinator], SensorEntity):
    """Representation of a SAJ sensor."""

    def __init__(
        self,
        coordinator: SAJDataUpdateCoordinator,
        serialnumber: str | None,
        pysaj_sensor: pysaj.Sensor,
    ) -> None:
        """Initialize the SAJ sensor."""
        super().__init__(coordinator)
        self._sensor = pysaj_sensor

        if pysaj_sensor.name in ("current_power", "temperature"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if pysaj_sensor.name == "total_yield":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self._attr_unique_id = f"{serialnumber}_{pysaj_sensor.name}"
        native_uom = SAJ_UNIT_MAPPINGS[pysaj_sensor.unit]
        self._attr_native_unit_of_measurement = native_uom
        self._attr_name = f"saj_{pysaj_sensor.name}"
        if native_uom == UnitOfPower.WATT:
            self._attr_device_class = SensorDeviceClass.POWER
        if native_uom == UnitOfEnergy.KILO_WATT_HOUR:
            self._attr_device_class = SensorDeviceClass.ENERGY
        if native_uom in (
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._sensor.value
