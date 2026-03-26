"""SAJ solar inverter interface."""

from __future__ import annotations

from datetime import date

import pysaj
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    EntityCategory,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import SAJConfigEntry, SAJRuntimeData
from .const import CONNECTION_TYPES, DOMAIN, INTEGRATION_TITLE

# Stable translation_key / unique_id suffixes (see strings.json entity.sensor.*).
DIAG_KEY_IP = "ip_address"
DIAG_KEY_CONNECTION_TYPE = "connection_type"
DIAG_KEY_SERIAL_NUMBER = "serial_number"

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
    runtime = entry.runtime_data
    saj = runtime.saj
    sensor_def = runtime.sensor_def

    hass_sensors = [
        SAJsensor(runtime, saj.serialnumber, sensor, inverter_name=None)
        for sensor in sensor_def
        if sensor.enabled
    ]

    diagnostic_sensors = [
        SAJDiagnosticSensor(entry, DIAG_KEY_IP, entry.data[CONF_HOST]),
        SAJDiagnosticSensor(entry, DIAG_KEY_CONNECTION_TYPE, entry.data[CONF_TYPE]),
        SAJDiagnosticSensor(
            entry, DIAG_KEY_SERIAL_NUMBER, saj.serialnumber or "Unknown"
        ),
    ]

    entities: list[SensorEntity] = [*hass_sensors, *diagnostic_sensors]
    async_add_entities(entities)


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
        "deprecated_yaml",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


class SAJsensor(SensorEntity):
    """Representation of a SAJ sensor."""

    _attr_should_poll = False
    _state: StateType

    def __init__(
        self,
        runtime: SAJRuntimeData,
        serialnumber: str | None,
        pysaj_sensor: pysaj.Sensor,
        inverter_name: str | None = None,
    ) -> None:
        """Initialize the SAJ sensor."""
        self._runtime = runtime
        self._sensor = pysaj_sensor
        self._inverter_name = inverter_name
        self._serialnumber = serialnumber
        self._state = self._sensor.value

        if pysaj_sensor.name in ("current_power", "temperature"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if pysaj_sensor.name == "total_yield":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self._attr_unique_id = f"{serialnumber}_{pysaj_sensor.name}"
        native_uom = SAJ_UNIT_MAPPINGS[pysaj_sensor.unit]
        self._attr_native_unit_of_measurement = native_uom
        if self._inverter_name:
            self._attr_name = f"saj_{self._inverter_name}_{pysaj_sensor.name}"
        else:
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

    async def async_added_to_hass(self) -> None:
        """Register for inverter poll updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._runtime.polling.async_add_poll_listener(self._on_poll_success)
        )

    @property
    def available(self) -> bool:
        """Keep reporting entity state; unknown values use None (same as before coordinator)."""
        return True

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def per_day_basis(self) -> bool:
        """Return if the sensors value is on daily basis or not."""
        return self._sensor.per_day_basis

    @property
    def per_total_basis(self) -> bool:
        """Return if the sensors value is cumulative or not."""
        return self._sensor.per_total_basis

    @property
    def date_updated(self) -> date:
        """Return the date when the sensor was last updated."""
        return self._sensor.date

    @callback
    def _on_poll_success(self, success: bool) -> None:
        """Update state from the inverter after a poll."""
        state_unknown = False
        if not success and (
            (self.per_day_basis and date.today() > self.date_updated)
            or (not self.per_day_basis and not self.per_total_basis)
        ):
            state_unknown = True

        update = False
        if self._sensor.value != self._state:
            update = True
            self._state = self._sensor.value

        if state_unknown and self._state is not None:
            update = True
            self._state = None

        if update:
            self.async_write_ha_state()


class SAJDiagnosticSensor(SensorEntity):
    """Representation of a SAJ diagnostic sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        translation_key: str,
        value: str | None,
    ) -> None:
        """Initialize the SAJ diagnostic sensor."""
        self._attr_unique_id = f"{entry.entry_id}_{translation_key}"
        self._attr_translation_key = translation_key
        self._attr_native_value = value

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return (
            str(self._attr_native_value)
            if self._attr_native_value is not None
            else None
        )
