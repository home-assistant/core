"""Support for monitoring emoncms feeds."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_API_KEY,
    CONF_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import sensor_name
from .const import (
    CONF_EXCLUDE_FEEDID,
    CONF_ONLY_INCLUDE_FEEDID,
    DOMAIN,
    FEED_ID,
    FEED_NAME,
    FEED_TAG,
)
from .coordinator import EmoncmsCoordinator

SENSORS: dict[str | None, SensorEntityDescription] = {
    "kWh": SensorEntityDescription(
        key="energy|kWh",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "Wh": SensorEntityDescription(
        key="energy|Wh",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "kW": SensorEntityDescription(
        key="power|kW",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "W": SensorEntityDescription(
        key="power|W",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V": SensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "A": SensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VA": SensorEntityDescription(
        key="apparent_power",
        translation_key="apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "°C": SensorEntityDescription(
        key="temperature|celsius",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "°F": SensorEntityDescription(
        key="temperature|fahrenheit",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "K": SensorEntityDescription(
        key="temperature|kelvin",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "Hz": SensorEntityDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "hPa": SensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "dB": SensorEntityDescription(
        key="decibel",
        translation_key="decibel",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "m³": SensorEntityDescription(
        key="volume|cubic_meter",
        translation_key="volume",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "m³/h": SensorEntityDescription(
        key="flow|cubic_meters_per_hour",
        translation_key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "l/m": SensorEntityDescription(
        key="flow|liters_per_minute",
        translation_key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "m/s": SensorEntityDescription(
        key="speed|meters_per_second",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "µg/m³": SensorEntityDescription(
        key="concentration|microgram_per_cubic_meter",
        translation_key="concentration",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ppm": SensorEntityDescription(
        key="concentration|microgram_parts_per_million",
        translation_key="concentration",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "%": SensorEntityDescription(
        key="percent",
        translation_key="percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

ATTR_FEEDID = "FeedId"
ATTR_FEEDNAME = "FeedName"
ATTR_LASTUPDATETIME = "LastUpdated"
ATTR_LASTUPDATETIMESTR = "LastUpdatedStr"
ATTR_SIZE = "Size"
ATTR_TAG = "Tag"
ATTR_USERID = "UserId"
CONF_SENSOR_NAMES = "sensor_names"
DECIMALS = 2
DEFAULT_UNIT = UnitOfPower.WATT

ONLY_INCL_EXCL_NONE = "only_include_exclude_or_none"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
        vol.Exclusive(CONF_ONLY_INCLUDE_FEEDID, ONLY_INCL_EXCL_NONE): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Exclusive(CONF_EXCLUDE_FEEDID, ONLY_INCL_EXCL_NONE): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Optional(CONF_SENSOR_NAMES): vol.All(
            {cv.positive_int: vol.All(cv.string, vol.Length(min=1))}
        ),
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DEFAULT_UNIT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import config from yaml."""
    if CONF_VALUE_TEMPLATE in config:
        async_create_issue(
            hass,
            DOMAIN,
            f"remove_{CONF_VALUE_TEMPLATE}_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.ERROR,
            translation_key=f"remove_{CONF_VALUE_TEMPLATE}",
            translation_placeholders={
                "domain": DOMAIN,
                "parameter": CONF_VALUE_TEMPLATE,
            },
        )
        return
    if CONF_ONLY_INCLUDE_FEEDID not in config:
        async_create_issue(
            hass,
            DOMAIN,
            f"missing_{CONF_ONLY_INCLUDE_FEEDID}_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"missing_{CONF_ONLY_INCLUDE_FEEDID}",
            translation_placeholders={
                "domain": DOMAIN,
            },
        )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") == FlowResultType.CREATE_ENTRY
        or result.get("reason") == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2025.3.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "emoncms",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the emoncms sensors."""
    name = sensor_name(entry.data[CONF_URL])
    exclude_feeds = entry.data.get(CONF_EXCLUDE_FEEDID)
    include_only_feeds = entry.options.get(
        CONF_ONLY_INCLUDE_FEEDID, entry.data.get(CONF_ONLY_INCLUDE_FEEDID)
    )

    if exclude_feeds is None and include_only_feeds is None:
        return

    coordinator = entry.runtime_data
    # uuid was added in emoncms database 11.5.7
    unique_id = entry.unique_id if entry.unique_id else entry.entry_id
    elems = coordinator.data
    if not elems:
        return
    sensors: list[EmonCmsSensor] = []

    for idx, elem in enumerate(elems):
        if include_only_feeds is not None and elem[FEED_ID] not in include_only_feeds:
            continue
        sensors.append(
            EmonCmsSensor(
                coordinator,
                unique_id,
                elem.get("unit"),
                name,
                idx,
            )
        )
    async_add_entities(sensors)


class EmonCmsSensor(CoordinatorEntity[EmoncmsCoordinator], SensorEntity):
    """Implementation of an Emoncms sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EmoncmsCoordinator,
        unique_id: str,
        unit_of_measurement: str | None,
        name: str,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        elem = {}
        if self.coordinator.data:
            elem = self.coordinator.data[self.idx]
        self._attr_translation_placeholders = {
            "emoncms_details": f"{elem[FEED_TAG]} {elem[FEED_NAME]}",
        }
        self._attr_unique_id = f"{unique_id}-{elem[FEED_ID]}"
        description = SENSORS.get(unit_of_measurement)
        if description is not None:
            self.entity_description = description
        else:
            self._attr_native_unit_of_measurement = unit_of_measurement
            self._attr_name = f"{name} {elem[FEED_NAME]}"
        self._update_attributes(elem)

    def _update_attributes(self, elem: dict[str, Any]) -> None:
        """Update entity attributes."""
        self._attr_extra_state_attributes = {
            ATTR_FEEDID: elem[FEED_ID],
            ATTR_TAG: elem[FEED_TAG],
            ATTR_FEEDNAME: elem[FEED_NAME],
        }
        if elem["value"] is not None:
            self._attr_extra_state_attributes[ATTR_SIZE] = elem["size"]
            self._attr_extra_state_attributes[ATTR_USERID] = elem["userid"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIME] = elem["time"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIMESTR] = (
                template.timestamp_local(float(elem["time"]))
            )

        self._attr_native_value = None
        if elem["value"] is not None:
            self._attr_native_value = round(float(elem["value"]), DECIMALS)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data:
            self._update_attributes(data[self.idx])
        super()._handle_coordinator_update()
