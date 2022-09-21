"""Support gathering ted5000 information."""
from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
import logging

import requests
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_HIDDEN,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PORT,
    CURRENCY_DOLLAR,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TIME_DAYS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ted"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default="base"): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ted5000 platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    mode = config.get(CONF_MODE)
    url = f"http://{host}:{port}/api/LiveData.xml"

    gateway = Ted5000Gateway(url)

    # Get MTU information to create the sensors.
    gateway.update()

    dev_mtus = []
    dev_utility = []

    # Create MTU sensors
    for mtu in gateway.data:
        dev_mtus.append(Ted5000Sensor(gateway, name, mtu, 0, POWER_WATT))
        dev_mtus.append(Ted5000Sensor(gateway, name, mtu, 1, ELECTRIC_POTENTIAL_VOLT))
        if mode in {"advanced", "extended"}:  # advanced or extended
            dev_mtus.append(Ted5000Sensor(gateway, name, mtu, 2, ENERGY_KILO_WATT_HOUR))
            dev_mtus.append(Ted5000Sensor(gateway, name, mtu, 3, ENERGY_KILO_WATT_HOUR))
            dev_mtus.append(Ted5000Sensor(gateway, name, mtu, 4, PERCENTAGE))

    # Create utility sensors
    if mode == "extended":  # extended only
        # MTUs Quantity
        dev_utility.append(Ted5000Utility(gateway, name, 0, ATTR_HIDDEN))
        # Current Rate $/kWh
        dev_utility.append(Ted5000Utility(gateway, name, 1, CURRENCY_DOLLAR))
        # Days left in billing cycle
        dev_utility.append(Ted5000Utility(gateway, name, 2, TIME_DAYS))
        # Plan type (Flat, Tier, TOU, Tier+TOU)
        dev_utility.append(Ted5000Utility(gateway, name, 3, ATTR_HIDDEN))
        # Current Tier (0 = Disabled)
        dev_utility.append(Ted5000Utility(gateway, name, 4, ATTR_HIDDEN))
        # Current TOU (0 = Disabled)
        dev_utility.append(Ted5000Utility(gateway, name, 5, ATTR_HIDDEN))
        # Current TOU Description (if Current TOU is 0 => Not Configured)
        dev_utility.append(Ted5000Utility(gateway, name, 6, ATTR_HIDDEN))
        # Carbon Rate lbs/kW
        dev_utility.append(Ted5000Utility(gateway, name, 7, ATTR_HIDDEN))
        # Meter read date
        dev_utility.append(Ted5000Utility(gateway, name, 8, ATTR_HIDDEN))

    add_entities(dev_mtus)
    add_entities(dev_utility)


class Ted5000Sensor(SensorEntity):
    """Implementation of a Ted5000 MTU sensor."""

    def __init__(self, gateway, name, mtu, ptr, unit):
        """Initialize the sensor."""
        dclass = {
            POWER_WATT: SensorDeviceClass.POWER,
            ELECTRIC_POTENTIAL_VOLT: SensorDeviceClass.VOLTAGE,
            ENERGY_KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
            PERCENTAGE: SensorDeviceClass.POWER_FACTOR,
        }
        sclass = {
            POWER_WATT: SensorStateClass.MEASUREMENT,
            ELECTRIC_POTENTIAL_VOLT: SensorStateClass.MEASUREMENT,
            ENERGY_KILO_WATT_HOUR: SensorStateClass.TOTAL_INCREASING,
            PERCENTAGE: SensorStateClass.MEASUREMENT,
        }
        suffix = {
            0: "power",
            1: "voltage",
            2: "energy_daily",
            3: "energy_monthly",
            4: "pf",
        }
        self._gateway = gateway
        self._name = f"{name} mtu{mtu} {suffix[ptr]}"
        self._mtu = mtu
        self._ptr = ptr
        self._unit = unit
        self._dclass = dclass[unit]
        self._sclass = sclass[unit]
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def device_class(self):
        """Return the device class the value is expressed in."""
        return self._dclass

    @property
    def state_class(self):
        """Return the state class the value is expressed in."""
        return self._sclass

    @property
    def native_value(self):
        """Return the state of the resources."""
        with suppress(KeyError):
            return self._gateway.data[self._mtu][self._ptr]

    def update(self):
        """Get the latest data from REST API."""
        self._gateway.update()


class Ted5000Utility(SensorEntity):
    """Implementation of a Ted5000 utility sensors."""

    def __init__(self, gateway, name, ptr, unit):
        """Initialize the sensor."""
        dclass = {
            ATTR_HIDDEN: ATTR_HIDDEN,
            CURRENCY_DOLLAR: SensorDeviceClass.MONETARY,
            TIME_DAYS: ATTR_HIDDEN,
        }
        sclass = {
            ATTR_HIDDEN: ATTR_HIDDEN,
            CURRENCY_DOLLAR: SensorStateClass.MEASUREMENT,
            TIME_DAYS: ATTR_HIDDEN,
        }
        units = {
            0: ATTR_HIDDEN,
            1: "$/kWh",
            2: TIME_DAYS,
            3: ATTR_HIDDEN,
            4: ATTR_HIDDEN,
            5: ATTR_HIDDEN,
            6: ATTR_HIDDEN,
            7: "lbs/kW",
            8: ATTR_HIDDEN,
        }
        suffix = {
            0: "MTUs",
            1: "CurrentRate",
            2: "DaysLeftInBillingCycle",
            3: "PlanType",
            4: "CurrentTier",
            5: "CurrentTOU",
            6: "CurrentTOUDescription",
            7: "CarbonRate",
            8: "MeterReadDate",
        }
        self._gateway = gateway
        self._name = f"{name} Utility {suffix[ptr]}"
        self._ptr = ptr
        self._unit = units[ptr]
        self._dclass = dclass[unit]
        self._sclass = sclass[unit]
        self.update()

    @property
    def name(self):
        """Return the friendly_name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._unit is not ATTR_HIDDEN:
            return self._unit

    @property
    def device_class(self):
        """Return the device class the value is expressed in."""
        if self._dclass is not ATTR_HIDDEN:
            return self._dclass

    @property
    def state_class(self):
        """Return the state class the value is expressed in."""
        if self._sclass is not ATTR_HIDDEN:
            return self._sclass

    @property
    def native_value(self):
        """Return the state of the resources."""
        with suppress(KeyError):
            return self._gateway.data_utility[self._ptr]

    def update(self) -> None:
        """Get the latest data from REST API."""
        self._gateway.update()


class Ted5000Gateway:
    """The class for handling the data retrieval."""

    def __init__(self, url):
        """Initialize the data object."""
        self.url = url
        self.data = {}
        self.data_utility = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Ted5000 XML API."""

        try:
            request = requests.get(self.url, timeout=10)
        except requests.exceptions.RequestException as err:
            _LOGGER.error("No connection to endpoint: %s", err)
        else:
            doc = xmltodict.parse(request.text)
            mtus = int(doc["LiveData"]["System"]["NumberMTU"])

            # MTU data
            for mtu in range(1, mtus + 1):
                power = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerNow"])
                voltage = int(doc["LiveData"]["Voltage"]["MTU%d" % mtu]["VoltageNow"])
                energy_tdy = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerTDY"])
                energy_mtd = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PowerMTD"])
                power_factor = int(doc["LiveData"]["Power"]["MTU%d" % mtu]["PF"])

                self.data[mtu] = {
                    0: power,
                    1: voltage / 10,
                    2: energy_tdy / 1000,
                    3: energy_mtd / 1000,
                    4: power_factor / 10,
                }

            # Utility Data
            current_rate = int(doc["LiveData"]["Utility"]["CurrentRate"])
            days_left = int(doc["LiveData"]["Utility"]["DaysLeftInBillingCycle"])
            plan_type = int(doc["LiveData"]["Utility"]["PlanType"])
            plan_type_str = {0: "Flat", 1: "Tier", 2: "TOU", 3: "Tier+TOU"}
            carbon_rate = int(doc["LiveData"]["Utility"]["CarbonRate"])
            read_date = int(doc["LiveData"]["Utility"]["MeterReadDate"])

            if plan_type in (0, 2):
                current_tier = 0
            else:
                current_tier = int(doc["LiveData"]["Utility"]["CurrentTier"]) + 1

            if plan_type < 2:
                current_tou = 0
                current_tou_str = "Not Configured"
            else:
                current_tou = int(doc["LiveData"]["Utility"]["CurrentTOU"]) + 1
                current_tou_str = doc["LiveData"]["Utility"]["CurrentTOUDescription"]

            self.data_utility = {
                0: mtus,
                1: current_rate / 100000,
                2: days_left,
                3: plan_type_str[plan_type],
                4: current_tier,
                5: current_tou,
                6: current_tou_str,
                7: carbon_rate / 100,
                8: read_date,
            }
