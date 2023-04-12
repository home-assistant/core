"""The Victron Bluetooth Low Energy integration."""
from __future__ import annotations

import logging

from bluetooth_sensor_state_data import BluetoothData
from construct.core import StreamError
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import DeviceClass, Units
from victron_ble.devices import (
    BatteryMonitor,
    BatteryMonitorData,
    DcEnergyMeter,
    DcEnergyMeterData,
    Device,
    SolarCharger,
    SolarChargerData,
    VEBus,
    VEBusData,
    detect_device_type,
)

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VICTRON_IDENTIFIER

_LOGGER = logging.getLogger(__name__)


class VictronBluetoothDeviceData(BluetoothData):
    """Class to hold Victron BLE device data."""

    def __init__(self, advertisement_key: str | None = None) -> None:
        """Initialize the Victron Bluetooth device data with an encryption key."""
        super().__init__()
        self._advertisement_key: str | None = advertisement_key
        self._parser: Device | None = None

    def validate_advertisement_key(self, data: bytes) -> bool:
        """Validate the advertisement key."""
        if not self._advertisement_key:
            _LOGGER.debug("Advertisement key not set")
            return False

        parser = detect_device_type(data)
        if parser is None:
            _LOGGER.error("Unable to detect device type")
            return False

        parsed_data = parser.PARSER.parse(data)
        if parsed_data is None:
            _LOGGER.error("Unable to parse data")
            return False

        encrypted_data = parsed_data.encrypted_data

        if encrypted_data[0] != bytes.fromhex(self._advertisement_key)[0]:
            # only possible check is whether the first byte matches
            _LOGGER.error("Advertisement key does not match")
            return False

        return True

    def _start_update(self, data: BluetoothServiceInfo) -> None:
        try:
            raw_data = data.manufacturer_data[VICTRON_IDENTIFIER]
        except (KeyError, IndexError):
            _LOGGER.debug("No manufacturer data for Victron")
            return

        if not self._parser:
            try:
                parser = detect_device_type(raw_data)
            except StreamError:
                _LOGGER.debug("Malformed advertisement %s", raw_data.hex())
                return
            if parser is None:
                _LOGGER.debug("Unsupported device type")
                return
            if not issubclass(
                parser, (BatteryMonitor, DcEnergyMeter, SolarCharger, VEBus)
            ):
                _LOGGER.debug("Unsupported device type")
                return
            self.set_device_manufacturer(data.manufacturer or "Victron")
            self.set_device_name(data.name)
            self.set_device_type(parser.__name__)
            if not self.validate_advertisement_key(raw_data):
                return
            assert self._advertisement_key is not None  # keep pylance happy
            self._parser = parser(self._advertisement_key)

        parsed_data = self._parser.parse(raw_data)
        if parsed_data is None:
            _LOGGER.debug("Unable to parse data")
            return
        if isinstance(parsed_data, BatteryMonitorData):
            self._update_battery_monitor(parsed_data)
        elif isinstance(parsed_data, DcEnergyMeterData):
            self._update_dc_energy_meter(parsed_data)
        elif isinstance(parsed_data, SolarChargerData):
            self._update_solar_charger(parsed_data)
        elif isinstance(parsed_data, VEBusData):
            self._update_vebus(parsed_data)

    def _update_battery_monitor(self, data: BatteryMonitorData) -> None:
        self.update_sensor(
            "Remaining Minutes",
            Units.TIME_MINUTES,
            data.get_remaining_mins(),
            DeviceClass.DURATION,
        )
        self.update_sensor(
            "Current",
            Units.ELECTRIC_CURRENT_AMPERE,
            data.get_current(),
            DeviceClass.CURRENT,
        )
        self.update_sensor(
            "Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_voltage(),
            DeviceClass.VOLTAGE,
        )
        self.update_sensor(
            "State of Charge",
            Units.PERCENTAGE,
            data.get_soc(),
            DeviceClass.BATTERY,
        )
        self.update_sensor(
            "Consumed Amp Hours",
            Units.ELECTRIC_CURRENT_FLOW_AMPERE_HOURS,
            data.get_consumed_ah(),
            DeviceClass.CURRENT_FLOW,
        )
        alarm = data.get_alarm()
        if alarm is not None:
            alarm = alarm.name
        else:
            alarm = "no alarm"
        self.update_sensor(
            "Alarm",
            None,
            alarm,
        )
        self.update_sensor(
            "Aux Mode",
            None,
            data.get_aux_mode().name,
        )
        self.update_sensor(
            "Temperature",
            Units.TEMP_CELSIUS,
            data.get_temperature(),
            DeviceClass.TEMPERATURE,
        )
        self.update_sensor(
            "Secondary Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_starter_voltage(),
            DeviceClass.VOLTAGE,
        )
        self.update_sensor(
            "Midpoint Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_midpoint_voltage(),
            DeviceClass.VOLTAGE,
        )

    def _update_dc_energy_meter(self, data: DcEnergyMeterData) -> None:
        meter_type = data.get_meter_type()
        if meter_type is not None:
            meter_type = meter_type.name
        self.update_sensor(
            "Type",
            None,
            meter_type,
        )
        self.update_sensor(
            "Current",
            Units.ELECTRIC_CURRENT_AMPERE,
            data.get_current(),
            DeviceClass.CURRENT,
        )
        self.update_sensor(
            "Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_voltage(),
            DeviceClass.VOLTAGE,
        )
        alarm = data.get_alarm()
        if alarm is not None:
            alarm = alarm.name
        else:
            alarm = "no alarm"
        self.update_sensor(
            "Alarm",
            None,
            alarm,
        )
        self.update_sensor(
            "Temperature",
            Units.TEMP_CELSIUS,
            data.get_temperature(),
            DeviceClass.TEMPERATURE,
        )
        self.update_sensor(
            "Aux Mode",
            None,
            data.get_aux_mode().name,
        )
        self.update_sensor(
            "Temperature",
            Units.TEMP_CELSIUS,
            data.get_temperature(),
            DeviceClass.TEMPERATURE,
        )
        self.update_sensor(
            "Secondary Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_starter_voltage(),
            DeviceClass.VOLTAGE,
        )

    def _update_solar_charger(self, data: SolarChargerData) -> None:
        charge_state = data.get_charge_state()
        if charge_state is not None:
            charge_state = charge_state.name
        self.update_sensor(
            "State",
            None,
            charge_state,
        )
        self.update_sensor(
            "Battery Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_battery_voltage(),
            DeviceClass.VOLTAGE,
        )
        self.update_sensor(
            "Battery Current",
            Units.ELECTRIC_CURRENT_AMPERE,
            data.get_battery_charging_current(),
            DeviceClass.CURRENT,
        )
        self.update_sensor(
            "Yield Today",
            Units.ENERGY_WATT_HOUR,
            data.get_yield_today(),
            DeviceClass.ENERGY,
        )
        self.update_sensor(
            "Power",
            Units.POWER_WATT,
            data.get_solar_power(),
            DeviceClass.POWER,
        )
        self.update_sensor(
            "External Device Load",
            Units.ELECTRIC_CURRENT_AMPERE,
            data.get_external_device_load(),
            DeviceClass.CURRENT,
        )

    def _update_vebus(self, data: VEBusData) -> None:
        device_state = data.get_device_state()
        if device_state is not None:
            device_state = device_state.name
        self.update_sensor(
            "Device State",
            None,
            device_state,
        )
        ac_in_state = data.get_ac_in_state()
        if ac_in_state is not None:
            ac_in_state = ac_in_state.name
        self.update_sensor(
            "AC In State",
            None,
            ac_in_state,
        )
        self.update_sensor(
            "AC In Power",
            Units.POWER_WATT,
            data.get_ac_in_power(),
            DeviceClass.POWER,
        )
        self.update_sensor(
            "AC Out Power",
            Units.POWER_WATT,
            data.get_ac_out_power(),
            DeviceClass.POWER,
        )
        self.update_sensor(
            "Battery Current",
            Units.ELECTRIC_CURRENT_AMPERE,
            data.get_battery_current(),
            DeviceClass.CURRENT,
        )
        self.update_sensor(
            "Battery Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_battery_voltage(),
            DeviceClass.VOLTAGE,
        )
        self.update_sensor(
            "Battery Temperature",
            Units.TEMP_CELSIUS,
            data.get_battery_temperature(),
            DeviceClass.TEMPERATURE,
        )
        self.update_sensor(
            "State of Charge",
            Units.PERCENTAGE,
            data.get_soc(),
            DeviceClass.BATTERY,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    key = entry.data[CONF_ACCESS_TOKEN]
    data = VictronBluetoothDeviceData(key)
    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=data.update,
    )

    await hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = False

    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, Platform.SENSOR
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
