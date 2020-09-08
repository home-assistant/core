"""Support for Renault sensors."""
import logging

from pyze.api import ChargeState, PlugState

from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE, POWER_KILO_WATT
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util.distance import LENGTH_KILOMETERS, LENGTH_MILES
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from .const import DOMAIN
from .pyzeproxy import PyzeProxy
from .pyzevehicleproxy import PyzeVehicleProxy
from .renaultentity import RenaultBatteryDataEntity

ATTR_BATTERY_AVAILABLE_ENERGY = "battery_available_energy"
ATTR_BATTERY_TEMPERATURE = "battery_temperature"
ATTR_CHARGING_POWER = "charging_power"
ATTR_CHARGING_REMAINING_TIME = "charging_remaining_time"
ATTR_PLUGGED = "plugged"
ATTR_PLUG_STATUS = "plug_status"

LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up platforms."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Renault entities from config entry."""
    proxy = hass.data[DOMAIN][config_entry.unique_id]
    entities = await get_entities(hass, proxy)
    proxy.entities.extend(entities)
    async_add_entities(entities, True)


async def get_entities(hass, proxy: PyzeProxy):
    """Create Renault entities for all vehicles."""
    entities = []
    for vehicle_link in proxy.get_vehicle_links():
        vehicle_proxy = await proxy.get_vehicle_proxy(vehicle_link)
        entities.extend(await get_vehicle_entities(hass, vehicle_proxy))
    return entities


async def get_vehicle_entities(hass, vehicle_proxy: PyzeVehicleProxy):
    """Create Renault entities for single vehicle."""
    entities = []
    entities.append(RenaultBatteryLevelSensor(vehicle_proxy, "Battery Level"))
    entities.append(RenaultChargeStateSensor(vehicle_proxy, "Charge State"))
    entities.append(RenaultChargingPowerSensor(vehicle_proxy, "Charging Power"))
    entities.append(RenaultPlugStateSensor(vehicle_proxy, "Plug State"))
    entities.append(RenaultRangeSensor(vehicle_proxy, "Range"))
    return entities


class RenaultBatteryLevelSensor(RenaultBatteryDataEntity):
    """Battery Level sensor."""

    @property
    def state(self):
        """Return the state of this entity."""
        data = self.coordinator.data
        if "batteryLevel" in data:
            return data.get("batteryLevel")
        LOGGER.warning("batteryLevel not available in coordinator data %s", data)

    @property
    def device_class(self):
        """Return the class of this entity."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return PERCENTAGE

    @property
    def icon(self):
        """Icon handling."""
        data = self.coordinator.data
        chargestate = data["chargingStatus"] == 1
        return icon_for_battery_level(battery_level=self.state, charging=chargestate)

    @property
    def device_state_attributes(self):
        """Return the state attributes of this entity."""
        attrs = {}
        attrs.update(super().device_state_attributes)
        data = self.coordinator.data
        if "batteryAvailableEnergy" in data:
            attrs[ATTR_BATTERY_AVAILABLE_ENERGY] = data["batteryAvailableEnergy"]
        if "batteryTemperature" in data:
            attrs[ATTR_BATTERY_TEMPERATURE] = data["batteryTemperature"]
        return attrs


class RenaultChargingRemainingTimeSensor(RenaultBatteryDataEntity):
    """Charging Remaining Time sensor."""

    @property
    def state(self):
        """Return the state of this entity."""
        data = self.coordinator.data
        if "chargingRemainingTime" in data:
            return data["chargingRemainingTime"]
        LOGGER.debug("chargingRemainingTime not available in coordinator data %s", data)
        return None


class RenaultChargingPowerSensor(RenaultBatteryDataEntity):
    """Charging Power sensor."""

    @property
    def state(self):
        """Return the state of this entity."""
        data = self.coordinator.data
        if "chargingInstantaneousPower" in data:
            return data["chargingInstantaneousPower"] / 1000
        LOGGER.debug(
            "chargingInstantaneousPower not available in coordinator data %s", data
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return POWER_KILO_WATT


class RenaultPlugStateSensor(RenaultBatteryDataEntity):
    """Plug State sensor."""

    @property
    def state(self):
        """Return the state of this entity."""
        data = self.coordinator.data
        if "plugStatus" in data:
            try:
                plug_state = PlugState(data["plugStatus"])
            except ValueError:
                plug_state = PlugState.NOT_AVAILABLE
            return plug_state.name
        LOGGER.debug("plugStatus not available in coordinator data %s", data)

    @property
    def icon(self):
        """Icon handling."""
        if self.state == PlugState.PLUGGED.name:
            return "mdi:power-plug"
        return "mdi:power-plug-off"


class RenaultChargeStateSensor(RenaultBatteryDataEntity):
    """Charge State sensor."""

    @property
    def state(self):
        """Return the state of this entity."""
        data = self.coordinator.data
        if "chargingStatus" in data:
            try:
                charge_state = ChargeState(data["chargingStatus"])
            except ValueError:
                charge_state = ChargeState.NOT_AVAILABLE
            return charge_state.name
        LOGGER.debug("chargingStatus not available in coordinator data %s", data)

    @property
    def icon(self):
        """Icon handling."""
        if self.state == ChargeState.CHARGE_IN_PROGRESS.name:
            return "mdi:flash"
        return "mdi:flash-off"


class RenaultRangeSensor(RenaultBatteryDataEntity):
    """Range sensor."""

    @property
    def state(self):
        """Return the state of this entity."""
        data = self.coordinator.data
        if "batteryAutonomy" in data:
            autonomy = data["batteryAutonomy"]
            if not self.hass.config.units.is_metric:
                autonomy = IMPERIAL_SYSTEM.length(autonomy, METRIC_SYSTEM.length_unit)
            return autonomy
        LOGGER.debug("batteryAutonomy not available in coordinator data %s", data)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        if not self.hass.config.units.is_metric:
            return LENGTH_MILES
        return LENGTH_KILOMETERS
