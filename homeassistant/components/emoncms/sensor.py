"""Support for monitoring emoncms feeds."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pyemoncms import EmoncmsClient
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_FEEDID,
    ATTR_FEEDNAME,
    ATTR_LASTUPDATETIME,
    ATTR_LASTUPDATETIMESTR,
    ATTR_SIZE,
    ATTR_TAG,
    ATTR_USERID,
)
from .coordinator import EmoncmsCoordinator

CONF_EXCLUDE_FEEDID = "exclude_feed_id"
CONF_ONLY_INCLUDE_FEEDID = "include_only_feed_id"
CONF_SENSOR_NAMES = "sensor_names"

DECIMALS = 2
DEFAULT_UNIT = UnitOfPower.WATT

ONLY_INCL_EXCL_NONE = "only_include_exclude_or_none"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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


SENSORS: dict[str | None, SensorEntityDescription] = {
    "kWh": SensorEntityDescription(
        key="energy|kWh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "Wh": SensorEntityDescription(
        key="energy|Wh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "W": SensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "%": SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V": SensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "A": SensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VA": SensorEntityDescription(
        key="apparentPower",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "°C": SensorEntityDescription(
        key="temperature|celsius",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "°F": SensorEntityDescription(
        key="temperature|fahrenheit",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "K": SensorEntityDescription(
        key="temperature|kelvin",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "Hz": SensorEntityDescription(
        key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "hPa": SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "dB": SensorEntityDescription(
        key="decibel",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Emoncms sensor."""
    apikey = config[CONF_API_KEY]
    url = config[CONF_URL]
    sensorid = config[CONF_ID]
    value_template = config.get(CONF_VALUE_TEMPLATE)
    config_unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    exclude_feeds = config.get(CONF_EXCLUDE_FEEDID)
    include_only_feeds = config.get(CONF_ONLY_INCLUDE_FEEDID)
    sensor_names = config.get(CONF_SENSOR_NAMES)
    scan_interval = config.get(CONF_SCAN_INTERVAL, timedelta(seconds=30))

    if value_template is not None:
        value_template.hass = hass

    emoncms_client = EmoncmsClient(url, apikey, session=async_get_clientsession(hass))
    coordinator = EmoncmsCoordinator(hass, emoncms_client, scan_interval)
    await coordinator.async_refresh()
    elems = coordinator.data
    if elems is None:
        return

    sensors: list[EmonCmsSensor] = []

    for idx, elem in enumerate(elems):
        if exclude_feeds is not None and int(elem["id"]) in exclude_feeds:
            continue

        if include_only_feeds is not None and int(elem["id"]) not in include_only_feeds:
            continue

        name = None
        if sensor_names is not None:
            name = sensor_names.get(int(elem["id"]), None)

        if unit := elem.get("unit"):
            unit_of_measurement = unit
        else:
            unit_of_measurement = config_unit

        sensors.append(
            EmonCmsSensor(
                coordinator,
                name,
                value_template,
                unit_of_measurement,
                str(sensorid),
                idx,
            )
        )
    async_add_entities(sensors)


class EmonCmsSensor(CoordinatorEntity[EmoncmsCoordinator], SensorEntity):
    """Implementation of an Emoncms sensor."""

    def __init__(
        self,
        coordinator: EmoncmsCoordinator,
        name: str | None,
        value_template: template.Template | None,
        unit_of_measurement: str | None,
        sensorid: str,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        elem = {}
        if self.coordinator.data:
            elem = self.coordinator.data[self.idx]
        if name is None:
            # Suppress ID in sensor name if it's 1, since most people won't
            # have more than one EmonCMS source and it's redundant to show the
            # ID if there's only one.
            id_for_name = "" if str(sensorid) == "1" else sensorid
            # Use the feed name assigned in EmonCMS or fall back to the feed ID
            feed_name = elem.get("name", f"Feed {elem.get('id')}")
            self._attr_name = f"EmonCMS{id_for_name} {feed_name}"
        else:
            self._attr_name = name
        self._value_template = value_template
        self._sensorid = sensorid

        params = SENSORS.get(unit_of_measurement)
        if params is not None:
            self._attr_device_class = params.device_class
            self._attr_native_unit_of_measurement = params.native_unit_of_measurement
            self._attr_state_class = params.state_class
        else:
            self._attr_native_unit_of_measurement = unit_of_measurement

        self._update_attributes(elem)

    def _update_attributes(self, elem: dict[str, Any]) -> None:
        """Update entity attributes."""
        self._attr_extra_state_attributes = {
            ATTR_FEEDID: elem["id"],
            ATTR_TAG: elem["tag"],
            ATTR_FEEDNAME: elem["name"],
        }
        if elem["value"] is not None:
            self._attr_extra_state_attributes[ATTR_SIZE] = elem["size"]
            self._attr_extra_state_attributes[ATTR_USERID] = elem["userid"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIME] = elem["time"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIMESTR] = (
                template.timestamp_local(float(elem["time"]))
            )

        self._attr_native_value = None
        if self._value_template is not None:
            self._attr_native_value = (
                self._value_template.render_with_possible_json_value(
                    elem["value"], STATE_UNKNOWN
                )
            )
        elif elem["value"] is not None:
            self._attr_native_value = round(float(elem["value"]), DECIMALS)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data:
            self._update_attributes(data[self.idx])
        super()._handle_coordinator_update()
