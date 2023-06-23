"""Simulates a battery to evaluate how much energy it could save."""
import logging, time

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback

from homeassistant.const import (
    CONF_NAME,
    UnitOfEnergy,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN
)

from .const import (
    CONF_BATTERY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_ENERGY_TARIFF,
    CONF_ENERGY_IMPORT_TARIFF,
    CONF_ENERGY_EXPORT_TARIFF,
    CONF_IMPORT_SENSOR,
    CONF_SECOND_IMPORT_SENSOR,
    CONF_SECOND_EXPORT_SENSOR,
    CONF_EXPORT_SENSOR,
    DOMAIN,
    BATTERY_PLATFORMS,
    OVERIDE_CHARGING,
    PAUSE_BATTERY,
    ATTR_ENERGY_SAVED,
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_BATTERY_IN, 
    CHARGING_RATE,
    DISCHARGING_RATE,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    ATTR_MONEY_SAVED,
    FORCE_DISCHARGE,
    BATTERY_MODE,
    MODE_IDLE,
    MODE_CHARGING,
    MODE_DISCHARGING,
    MODE_FORCE_CHARGING,
    MODE_FORCE_DISCHARGING,
    MODE_FULL,
    MODE_EMPTY,
    ATTR_MONEY_SAVED_IMPORT,
    ATTR_MONEY_SAVED_EXPORT,
    TARIFF_TYPE,
    NO_TARIFF_INFO,
    TARIFF_SENSOR_ENTITIES,
    FIXED_NUMERICAL_TARIFFS,
    BATTERY_CYCLES,
    CHARGE_ONLY
)

_LOGGER = logging.getLogger(__name__)

BATTERY_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_IMPORT_SENSOR): cv.entity_id,
            vol.Required(CONF_EXPORT_SENSOR): cv.entity_id,
            vol.Optional(CONF_ENERGY_TARIFF): cv.entity_id,
            vol.Optional(CONF_ENERGY_EXPORT_TARIFF): cv.entity_id,
            vol.Optional(CONF_ENERGY_IMPORT_TARIFF): cv.entity_id,
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_BATTERY_SIZE): vol.All(float),
            vol.Required(CONF_BATTERY_MAX_DISCHARGE_RATE): vol.All(float),
            vol.Optional(CONF_BATTERY_MAX_CHARGE_RATE, default=1.0): vol.All(float),
            vol.Optional(CONF_BATTERY_EFFICIENCY, default=1.0): vol.All(float),
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: BATTERY_CONFIG_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

async def async_setup(hass, config):
    """Set up battery platforms from a YAML."""
    hass.data.setdefault(DOMAIN, {})

    if config.get(DOMAIN)== None:
        return True
    for battery, conf in config.get(DOMAIN).items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, battery)
        handle = SimulatedBatteryHandle(conf, hass)
        if (battery in hass.data[DOMAIN]):
            _LOGGER.warning("Battery name not unique - not able to create.")
            continue
        hass.data[DOMAIN][battery] = handle

        for platform in BATTERY_PLATFORMS:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    platform,
                    DOMAIN,
                    [{CONF_BATTERY: battery, CONF_NAME: conf.get(CONF_NAME, battery)}],
                    config,
                )
            )
    return True

async def async_setup_entry(hass, entry) -> bool:
    """Set up battery platforms from a Config Flow Entry"""
    hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("Setup %s.%s", DOMAIN, entry.data[CONF_NAME])
    handle = SimulatedBatteryHandle(entry.data, hass)
    hass.data[DOMAIN][entry.entry_id] = handle

    # Forward the setup to the sensor platform.
    for platform in BATTERY_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True

class SimulatedBatteryHandle():
    """Representation of the battery itself"""

    def __init__(
        self,
        config,
        hass
    ):

        """Initialize the Battery."""
        self._hass = hass
        self._import_sensor_id = config[CONF_IMPORT_SENSOR]
        self._export_sensor_id = config[CONF_EXPORT_SENSOR]
        self._second_import_sensor_id = None
        self._second_export_sensor_id = None
        if (CONF_SECOND_IMPORT_SENSOR in config and
            len(config[CONF_SECOND_IMPORT_SENSOR]) > 6):
            self._second_import_sensor_id = config[CONF_SECOND_IMPORT_SENSOR]
        if (CONF_SECOND_EXPORT_SENSOR in config and
            len(config[CONF_SECOND_EXPORT_SENSOR]) > 6):
            self._second_export_sensor_id = config[CONF_SECOND_EXPORT_SENSOR]
        """Defalt to sensor entites for backwards compatibility"""
        self._tariff_type = TARIFF_SENSOR_ENTITIES
        if TARIFF_TYPE in config:
            self._tariff_type = config[TARIFF_TYPE]
        self._import_tariff_sensor_id = None
        if CONF_ENERGY_IMPORT_TARIFF in config:
            self._import_tariff_sensor_id = config[CONF_ENERGY_IMPORT_TARIFF]
        elif CONF_ENERGY_TARIFF in config:
            """For backwards compatibility"""
            self._import_tariff_sensor_id = config[CONF_ENERGY_TARIFF]
        self._export_tariff_sensor_id = None
        if CONF_ENERGY_EXPORT_TARIFF in config:
            self._export_tariff_sensor_id = config[CONF_ENERGY_EXPORT_TARIFF]
        self._date_recording_started = time.asctime()
        self._collecting1 = None
        self._collecting2 = None
        self._collecting3 = None
        self._charging = False
        self._name = config[CONF_NAME]
        self._battery_size = config[CONF_BATTERY_SIZE]
        self._max_discharge_rate = config[CONF_BATTERY_MAX_DISCHARGE_RATE]
        self._max_charge_rate = config[CONF_BATTERY_MAX_CHARGE_RATE]
        self._battery_efficiency = config[CONF_BATTERY_EFFICIENCY]
        self._last_import_reading_time = time.time()
        self._last_export_reading_time = time.time()
        self._last_battery_update_time = time.time()
        self._max_discharge = 0.0
        self._charge_percentage = 0.0
        self._charge_state = 0.0
        self._last_export_reading = 0.0
        self._last_import_cumulative_reading = 1.0
        self._switches = {
            OVERIDE_CHARGING: False, 
            PAUSE_BATTERY: False,
            FORCE_DISCHARGE: False,
            CHARGE_ONLY: False
            }
        self._sensors = {
            ATTR_ENERGY_SAVED: 0.0,
            ATTR_ENERGY_BATTERY_OUT: 0.0,
            ATTR_ENERGY_BATTERY_IN: 0.0,
            CHARGING_RATE: 0.0,
            DISCHARGING_RATE: 0.0,
            GRID_EXPORT_SIM: 0.0,
            GRID_IMPORT_SIM: 0.0,
            ATTR_MONEY_SAVED: 0.0,
            BATTERY_MODE: MODE_IDLE,
            ATTR_MONEY_SAVED_IMPORT: 0.0,
            ATTR_MONEY_SAVED_EXPORT: 0.0,
            BATTERY_CYCLES: 0.0
        }

        async_at_start(self._hass, self.async_source_tracking)
        async_dispatcher_connect(
            self._hass, f"{self._name}-BatteryResetMessage", self.async_reset_battery
        )
        async_dispatcher_connect(
            self._hass, f"{self._name}-BatteryResetImportSim", self.reset_import_sim_sensor
        )
        async_dispatcher_connect(
            self._hass, f"{self._name}-BatteryResetExportSim", self.reset_export_sim_sensor
        )

    def async_reset_battery(self):
        _LOGGER.debug("Reset battery")
        self.reset_import_sim_sensor()
        self.reset_export_sim_sensor()
        self._charge_state = 0.0
        self._sensors[ATTR_ENERGY_SAVED] = 0.0
        self._sensors[ATTR_MONEY_SAVED] = 0.0
        self._sensors[ATTR_ENERGY_BATTERY_OUT] = 0.0
        self._sensors[ATTR_ENERGY_BATTERY_IN] = 0.0
        self._sensors[ATTR_MONEY_SAVED_IMPORT] = 0.0
        self._sensors[ATTR_MONEY_SAVED_EXPORT] = 0.0
        self._energy_saved_today = 0.0
        self._energy_saved_week = 0.0
        self._energy_saved_month = 0.0
        self._date_recording_started = time.asctime()
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")
        return

    def reset_import_sim_sensor(self):
        _LOGGER.debug("Reset import sim sensor")
        if (self._hass.states.get(self._import_sensor_id).state is not None and
            self._hass.states.get(self._import_sensor_id).state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]):
            self._sensors[GRID_IMPORT_SIM] = float(self._hass.states.get(self._import_sensor_id).state)
        else:
            self._sensors[GRID_IMPORT_SIM] = 0.0
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")

    def reset_export_sim_sensor(self):
        _LOGGER.debug("Reset export sim sensor")
        if (self._hass.states.get(self._export_sensor_id).state is not None and
            self._hass.states.get(self._export_sensor_id).state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]):
            self._sensors[GRID_EXPORT_SIM] = float(self._hass.states.get(self._export_sensor_id).state)
        else:
            self._sensors[GRID_EXPORT_SIM] = 0.0
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")

    @callback
    def async_source_tracking(self, event):
        """Wait for source to be ready, then start."""
        self._collecting1 = async_track_state_change_event(
            self._hass, [self._import_sensor_id], self.async_import_reading
        )
        _LOGGER.debug("<%s> monitoring %s", self._name, self._import_sensor_id)
        if self._second_import_sensor_id != None:
            self._collecting3 = async_track_state_change_event(
                self._hass, [self._second_import_sensor_id], self.async_import_reading
            )
        _LOGGER.debug("<%s> monitoring %s", self._name, self._second_import_sensor_id)
        self._collecting2 = async_track_state_change_event(
            self._hass, [self._export_sensor_id], self.async_export_reading
        )
        _LOGGER.debug("<%s> monitoring %s", self._name, self._export_sensor_id)
        if self._second_export_sensor_id != None:
            self._collecting4 = async_track_state_change_event(
                self._hass, [self._second_export_sensor_id], self.async_export_reading
            )
        _LOGGER.debug("<%s> monitoring %s", self._name, self._second_export_sensor_id)

    @callback
    def async_export_reading(self, event):

        """Handle the source entity state changes."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if (old_state is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]):
            return

        units = self._hass.states.get(self._export_sensor_id).attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if units not in [UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.WATT_HOUR]:
            _LOGGER.warning("Units of import sensor not recognised - may give wrong results")
        conversion_factor = 1.0
        if units == UnitOfEnergy.WATT_HOUR:
            conversion_factor = 0.001

        export_amount = conversion_factor*(float(new_state.state) - float(old_state.state))

        if export_amount < 0:
            _LOGGER.warning("Export sensor value decreased - meter may have been reset")
            self._sensors[CHARGING_RATE] = 0
            self._last_export_reading_time = time.time()
            return

        if (self._last_import_reading_time>self._last_export_reading_time):
            if (self._last_export_reading > 0):
                _LOGGER.warning("Accumulated export reading not cleared error")
            self._last_export_reading = export_amount
        else:
            export_amount += self._last_export_reading
            self._last_export_reading = 0.0
            self.updateBattery(0.0, export_amount)
        self._last_export_reading_time = time.time()

    @callback
    def async_import_reading(self, event):

        """Handle the import sensor state changes - energy being imported from grid to be drawn from battery instead"""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        """If data missing return"""
        if (
            old_state is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            return

        self._last_import_reading_time = time.time()

        """Check units of import sensor and calculate import amount in kWh"""
        units = self._hass.states.get(self._import_sensor_id).attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if units not in [UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.WATT_HOUR]:
            _LOGGER.warning("Units of import sensor not recognised - may give wrong results")
        conversion_factor = 1.0
        if units == UnitOfEnergy.WATT_HOUR:
            conversion_factor = 0.001

        import_amount = conversion_factor*(float(new_state.state) - float(old_state.state))
        self._last_import_cumulative_reading = conversion_factor*(float(new_state.state))

        if import_amount < 0:
            _LOGGER.warning("Import sensor value decreased - meter may have been reset")
            self._sensors[DISCHARGING_RATE] = 0
            return

        self.updateBattery(import_amount, self._last_export_reading)
        self._last_export_reading = 0.0
    
    def getTariffReading(self, entity_id):
        if self._tariff_type == NO_TARIFF_INFO:
            return None
        elif self._tariff_type == FIXED_NUMERICAL_TARIFFS:
            return entity_id
        """Default behaviour - assume sensor entities"""
        if (entity_id is None or
            len(entity_id) < 6 or
            self._hass.states.get(entity_id) is None or
            self._hass.states.get(entity_id).state in [STATE_UNAVAILABLE, STATE_UNKNOWN]):
            return None
        return float(self._hass.states.get(entity_id).state)

    def updateBattery(self, import_amount, export_amount):
        _LOGGER.debug("Battery update event (%s). Import: %s, Export: %s", self._name, round(import_amount,4), round(export_amount,4))
        if self._charge_state=='unknown': self._charge_state = 0.0

        """Calculate maximum possible charge and discharge based on battery specifications and time since last discharge"""
        time_now = time.time()
        time_since_last_battery_update = time_now-self._last_battery_update_time
        max_discharge = time_since_last_battery_update*self._max_discharge_rate/3600
        max_charge = time_since_last_battery_update*self._max_charge_rate/3600
        available_capacity_to_charge = self._battery_size - float(self._charge_state)
        available_capacity_to_discharge = float(self._charge_state)*float(self._battery_efficiency)

        if self._switches[PAUSE_BATTERY]:
            _LOGGER.debug("Battery (%s) paused.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = 0.0
            net_export = export_amount
            net_import = import_amount
            self._sensors[BATTERY_MODE] = MODE_IDLE
        elif self._switches[OVERIDE_CHARGING]:
            _LOGGER.debug("Battery (%s) overide charging.", self._name)
            amount_to_charge = min(max_charge, available_capacity_to_charge)
            amount_to_discharge = 0.0
            net_export = max(export_amount - amount_to_charge, 0)
            net_import = max(amount_to_charge - export_amount, 0) + import_amount
            self._charging = True
            self._sensors[BATTERY_MODE] = MODE_FORCE_CHARGING
        elif self._switches[FORCE_DISCHARGE]:
            _LOGGER.debug("Battery (%s) forced discharging.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = min(max_discharge, available_capacity_to_discharge)
            net_export = max(amount_to_discharge - import_amount, 0) + export_amount
            net_import = max(import_amount - amount_to_discharge, 0)
            self._sensors[BATTERY_MODE] = MODE_FORCE_DISCHARGING
        elif self._switches[CHARGE_ONLY]:
            _LOGGER.debug("Battery (%s) charge only mode.", self._name)
            amount_to_charge = min(export_amount, max_charge, available_capacity_to_charge)
            amount_to_discharge = 0.0
            net_import = import_amount
            net_export = export_amount - amount_to_charge
            if amount_to_charge > amount_to_discharge:
                self._sensors[BATTERY_MODE] = MODE_CHARGING
            else:
                self._sensors[BATTERY_MODE] = MODE_IDLE
        else:
            _LOGGER.debug("Battery (%s) normal mode.", self._name)
            amount_to_charge = min(export_amount, max_charge, available_capacity_to_charge)
            amount_to_discharge = min(import_amount, max_discharge, available_capacity_to_discharge)
            net_import = import_amount - amount_to_discharge
            net_export = export_amount - amount_to_charge
            if amount_to_charge > amount_to_discharge:
                self._sensors[BATTERY_MODE] = MODE_CHARGING
            else:
                self._sensors[BATTERY_MODE] = MODE_DISCHARGING
        
        current_import_tariff = self.getTariffReading(self._import_tariff_sensor_id)
        current_export_tariff = self.getTariffReading(self._export_tariff_sensor_id)

        if current_import_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_IMPORT] += (import_amount - net_import)*current_import_tariff
        if current_export_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_EXPORT]  += (net_export - export_amount)*current_export_tariff
        if self._tariff_type is not NO_TARIFF_INFO:
            self._sensors[ATTR_MONEY_SAVED] = self._sensors[ATTR_MONEY_SAVED_IMPORT] + self._sensors[ATTR_MONEY_SAVED_EXPORT]

        self._charge_state = float(self._charge_state) + amount_to_charge - (amount_to_discharge/float(self._battery_efficiency))

        self._sensors[ATTR_ENERGY_SAVED] += import_amount - net_import
        self._sensors[GRID_IMPORT_SIM] += net_import
        self._sensors[GRID_EXPORT_SIM] += net_export
        self._sensors[ATTR_ENERGY_BATTERY_IN] += amount_to_charge
        self._sensors[ATTR_ENERGY_BATTERY_OUT] += amount_to_discharge
        self._sensors[CHARGING_RATE] = amount_to_charge/(time_since_last_battery_update/3600)
        self._sensors[DISCHARGING_RATE] = amount_to_discharge/(time_since_last_battery_update/3600)
        self._sensors[BATTERY_CYCLES] = self._sensors[ATTR_ENERGY_BATTERY_IN] / self._battery_size

        self._charge_percentage = round(100*self._charge_state/self._battery_size)

        if self._charge_percentage < 2:
            self._sensors[BATTERY_MODE] = MODE_EMPTY
        elif self._charge_percentage >98:
            self._sensors[BATTERY_MODE] = MODE_FULL

        """Reset day/week/month counters"""
        if time.strftime("%w") != time.strftime("%w", time.gmtime(self._last_battery_update_time)):
            self._energy_saved_today = 0
        if time.strftime("%U") != time.strftime("%U", time.gmtime(self._last_battery_update_time)):
            self._energy_saved_week = 0
        if time.strftime("%m") != time.strftime("%m", time.gmtime(self._last_battery_update_time)):
            self._energy_saved_month = 0

        self._last_battery_update_time = time_now
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")
        _LOGGER.debug("Battery update complete (%s). Sensors: %s", self._name, self._sensors)
