"""Support for APCUPSd sensors."""
from __future__ import annotations

import logging

from apcaccess.status import ALL_UNITS
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_RESOURCES,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, APCUPSdData

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, SensorEntityDescription] = {
    "alarmdel": SensorEntityDescription(
        key="alarmdel",
        name="UPS Alarm Delay",
        icon="mdi:alarm",
    ),
    "ambtemp": SensorEntityDescription(
        key="ambtemp",
        name="UPS Ambient Temperature",
        icon="mdi:thermometer",
    ),
    "apc": SensorEntityDescription(
        key="apc",
        name="UPS Status Data",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "apcmodel": SensorEntityDescription(
        key="apcmodel",
        name="UPS Model",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "badbatts": SensorEntityDescription(
        key="badbatts",
        name="UPS Bad Batteries",
        icon="mdi:information-outline",
    ),
    "battdate": SensorEntityDescription(
        key="battdate",
        name="UPS Battery Replaced",
        icon="mdi:calendar-clock",
    ),
    "battstat": SensorEntityDescription(
        key="battstat",
        name="UPS Battery Status",
        icon="mdi:information-outline",
    ),
    "battv": SensorEntityDescription(
        key="battv",
        name="UPS Battery Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "bcharge": SensorEntityDescription(
        key="bcharge",
        name="UPS Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    "cable": SensorEntityDescription(
        key="cable",
        name="UPS Cable Type",
        icon="mdi:ethernet-cable",
        entity_registry_enabled_default=False,
    ),
    "cumonbatt": SensorEntityDescription(
        key="cumonbatt",
        name="UPS Total Time on Battery",
        icon="mdi:timer-outline",
    ),
    "date": SensorEntityDescription(
        key="date",
        name="UPS Status Date",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    "dipsw": SensorEntityDescription(
        key="dipsw",
        name="UPS Dip Switch Settings",
        icon="mdi:information-outline",
    ),
    "dlowbatt": SensorEntityDescription(
        key="dlowbatt",
        name="UPS Low Battery Signal",
        icon="mdi:clock-alert",
    ),
    "driver": SensorEntityDescription(
        key="driver",
        name="UPS Driver",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "dshutd": SensorEntityDescription(
        key="dshutd",
        name="UPS Shutdown Delay",
        icon="mdi:timer-outline",
    ),
    "dwake": SensorEntityDescription(
        key="dwake",
        name="UPS Wake Delay",
        icon="mdi:timer-outline",
    ),
    "end apc": SensorEntityDescription(
        key="end apc",
        name="UPS Date and Time",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    "extbatts": SensorEntityDescription(
        key="extbatts",
        name="UPS External Batteries",
        icon="mdi:information-outline",
    ),
    "firmware": SensorEntityDescription(
        key="firmware",
        name="UPS Firmware Version",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "hitrans": SensorEntityDescription(
        key="hitrans",
        name="UPS Transfer High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "hostname": SensorEntityDescription(
        key="hostname",
        name="UPS Hostname",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="UPS Ambient Humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
    ),
    "itemp": SensorEntityDescription(
        key="itemp",
        name="UPS Internal Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "lastxfer": SensorEntityDescription(
        key="lastxfer",
        name="UPS Last Transfer",
        icon="mdi:transfer",
        entity_registry_enabled_default=False,
    ),
    "linefail": SensorEntityDescription(
        key="linefail",
        name="UPS Input Voltage Status",
        icon="mdi:information-outline",
    ),
    "linefreq": SensorEntityDescription(
        key="linefreq",
        name="UPS Line Frequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        icon="mdi:information-outline",
    ),
    "linev": SensorEntityDescription(
        key="linev",
        name="UPS Input Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "loadpct": SensorEntityDescription(
        key="loadpct",
        name="UPS Load",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
    ),
    "loadapnt": SensorEntityDescription(
        key="loadapnt",
        name="UPS Load Apparent Power",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:gauge",
    ),
    "lotrans": SensorEntityDescription(
        key="lotrans",
        name="UPS Transfer Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "mandate": SensorEntityDescription(
        key="mandate",
        name="UPS Manufacture Date",
        icon="mdi:calendar",
        entity_registry_enabled_default=False,
    ),
    "masterupd": SensorEntityDescription(
        key="masterupd",
        name="UPS Master Update",
        icon="mdi:information-outline",
    ),
    "maxlinev": SensorEntityDescription(
        key="maxlinev",
        name="UPS Input Voltage High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "maxtime": SensorEntityDescription(
        key="maxtime",
        name="UPS Battery Timeout",
        icon="mdi:timer-off-outline",
    ),
    "mbattchg": SensorEntityDescription(
        key="mbattchg",
        name="UPS Battery Shutdown",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
    ),
    "minlinev": SensorEntityDescription(
        key="minlinev",
        name="UPS Input Voltage Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "mintimel": SensorEntityDescription(
        key="mintimel",
        name="UPS Shutdown Time",
        icon="mdi:timer-outline",
    ),
    "model": SensorEntityDescription(
        key="model",
        name="UPS Model",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "nombattv": SensorEntityDescription(
        key="nombattv",
        name="UPS Battery Nominal Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "nominv": SensorEntityDescription(
        key="nominv",
        name="UPS Nominal Input Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "nomoutv": SensorEntityDescription(
        key="nomoutv",
        name="UPS Nominal Output Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "nompower": SensorEntityDescription(
        key="nompower",
        name="UPS Nominal Output Power",
        native_unit_of_measurement=POWER_WATT,
        icon="mdi:flash",
    ),
    "nomapnt": SensorEntityDescription(
        key="nomapnt",
        name="UPS Nominal Apparent Power",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
        icon="mdi:flash",
    ),
    "numxfers": SensorEntityDescription(
        key="numxfers",
        name="UPS Transfer Count",
        icon="mdi:counter",
    ),
    "outcurnt": SensorEntityDescription(
        key="outcurnt",
        name="UPS Output Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        icon="mdi:flash",
    ),
    "outputv": SensorEntityDescription(
        key="outputv",
        name="UPS Output Voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    "reg1": SensorEntityDescription(
        key="reg1",
        name="UPS Register 1 Fault",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "reg2": SensorEntityDescription(
        key="reg2",
        name="UPS Register 2 Fault",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "reg3": SensorEntityDescription(
        key="reg3",
        name="UPS Register 3 Fault",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "retpct": SensorEntityDescription(
        key="retpct",
        name="UPS Restore Requirement",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-alert",
    ),
    "selftest": SensorEntityDescription(
        key="selftest",
        name="UPS Last Self Test",
        icon="mdi:calendar-clock",
    ),
    "sense": SensorEntityDescription(
        key="sense",
        name="UPS Sensitivity",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "serialno": SensorEntityDescription(
        key="serialno",
        name="UPS Serial Number",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "starttime": SensorEntityDescription(
        key="starttime",
        name="UPS Startup Time",
        icon="mdi:calendar-clock",
    ),
    "statflag": SensorEntityDescription(
        key="statflag",
        name="UPS Status Flag",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "status": SensorEntityDescription(
        key="status",
        name="UPS Status",
        icon="mdi:information-outline",
    ),
    "stesti": SensorEntityDescription(
        key="stesti",
        name="UPS Self Test Interval",
        icon="mdi:information-outline",
    ),
    "timeleft": SensorEntityDescription(
        key="timeleft",
        name="UPS Time Left",
        icon="mdi:clock-alert",
    ),
    "tonbatt": SensorEntityDescription(
        key="tonbatt",
        name="UPS Time on Battery",
        icon="mdi:timer-outline",
    ),
    "upsmode": SensorEntityDescription(
        key="upsmode",
        name="UPS Mode",
        icon="mdi:information-outline",
    ),
    "upsname": SensorEntityDescription(
        key="upsname",
        name="UPS Name",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "version": SensorEntityDescription(
        key="version",
        name="UPS Daemon Info",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    "xoffbat": SensorEntityDescription(
        key="xoffbat",
        name="UPS Transfer from Battery",
        icon="mdi:transfer",
    ),
    "xoffbatt": SensorEntityDescription(
        key="xoffbatt",
        name="UPS Transfer from Battery",
        icon="mdi:transfer",
    ),
    "xonbatt": SensorEntityDescription(
        key="xonbatt",
        name="UPS Transfer to Battery",
        icon="mdi:transfer",
    ),
}

SPECIFIC_UNITS = {"ITEMP": TEMP_CELSIUS}
INFERRED_UNITS = {
    " Minutes": TIME_MINUTES,
    " Seconds": TIME_SECONDS,
    " Percent": PERCENTAGE,
    " Volts": ELECTRIC_POTENTIAL_VOLT,
    " Ampere": ELECTRIC_CURRENT_AMPERE,
    " Volt-Ampere": POWER_VOLT_AMPERE,
    " Watts": POWER_WATT,
    " Hz": FREQUENCY_HERTZ,
    " C": TEMP_CELSIUS,
    " Percent Load Capacity": PERCENTAGE,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCES, default=[]): vol.All(
            cv.ensure_list, [vol.In([desc.key for desc in SENSORS.values()])]
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the configurations from YAML to config flows."""
    # We only import configs from YAML if it hasn't been imported. If there is a config
    # entry marked with SOURCE_IMPORT, it means the YAML config has been imported.
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == SOURCE_IMPORT:
            return

    # This is the second step of YAML config imports, first see the comments in
    # async_setup() of __init__.py to get an idea of how we import the YAML configs.
    # Here we retrieve the partial YAML configs from the special entry id.
    conf = hass.data[DOMAIN].get(SOURCE_IMPORT)
    if conf is None:
        return

    _LOGGER.warning(
        "Configuration of apcupsd in YAML is deprecated and will be "
        "removed in Home Assistant 2022.12; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    # Remove the artificial entry since it's no longer needed.
    hass.data[DOMAIN].pop(SOURCE_IMPORT)

    # Our config flow supports CONF_RESOURCES and will properly import it to disable
    # entities not listed in CONF_RESOURCES by default. Note that this designed to
    # support YAML config import only (i.e., not shown in UI during setup).
    conf[CONF_RESOURCES] = config[CONF_RESOURCES]

    _LOGGER.debug(
        "YAML configurations loaded with host %s, port %s and resources %s",
        conf[CONF_HOST],
        conf[CONF_PORT],
        conf[CONF_RESOURCES],
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )

    return


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the APCUPSd sensors from config entries."""
    data_service: APCUPSdData = hass.data[DOMAIN][config_entry.entry_id]

    # The resources from data service are in upper-case by default, but we use
    # lower cases throughout this integration.
    available_resources: set[str] = {k.lower() for k, _ in data_service.status.items()}

    # We use user-specified resources from imported YAML config (if available) to
    # determine whether to enable the entity by default. Here, we first collect the
    # specified resources
    specified_resources = None
    if (resources := config_entry.data.get(CONF_RESOURCES)) is not None:
        assert isinstance(resources, list)
        specified_resources = set(resources)

    entities = []
    for resource in available_resources:
        if resource not in SENSORS:
            _LOGGER.warning("Invalid resource from APCUPSd: %s", resource.upper())
            continue

        # To avoid breaking changes, we disable sensors not specified in resources.
        description = SENSORS[resource]
        enabled_by_default = description.entity_registry_enabled_default
        if specified_resources is not None:
            enabled_by_default = resource in specified_resources

        entity = APCUPSdSensor(data_service, description, enabled_by_default)
        entities.append(entity)

    async_add_entities(entities, update_before_add=True)


def infer_unit(value):
    """If the value ends with any of the units from ALL_UNITS.

    Split the unit off the end of the value and return the value, unit tuple
    pair. Else return the original value and None as the unit.
    """

    for unit in ALL_UNITS:
        if value.endswith(unit):
            return value[: -len(unit)], INFERRED_UNITS.get(unit, unit.strip())
    return value, None


class APCUPSdSensor(SensorEntity):
    """Representation of a sensor entity for APCUPSd status values."""

    def __init__(
        self,
        data_service: APCUPSdData,
        description: SensorEntityDescription,
        enabled_by_default: bool,
    ) -> None:
        """Initialize the sensor."""
        # Set up unique id and device info if serial number is available.
        if (serial_no := data_service.serial_no) is not None:
            self._attr_unique_id = f"{serial_no}_{description.key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, serial_no)},
                model=data_service.model,
                manufacturer="APC",
                hw_version=data_service.hw_version,
                sw_version=data_service.sw_version,
            )

        self.entity_description = description
        self._attr_entity_registry_enabled_default = enabled_by_default
        self._data_service = data_service

    def update(self) -> None:
        """Get the latest status and use it to update our sensor state."""
        self._data_service.update()

        key = self.entity_description.key.upper()
        if key not in self._data_service.status:
            self._attr_native_value = None
            return

        self._attr_native_value, inferred_unit = infer_unit(
            self._data_service.status[key]
        )
        if not self.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = inferred_unit
