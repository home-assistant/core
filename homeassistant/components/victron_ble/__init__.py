"""The Victron Bluetooth Low Energy integration."""
from __future__ import annotations

import logging

from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import DeviceClass, Units
from victron_ble.devices import (
    BatteryMonitor,
    DcEnergyMeter,
    DeviceData,
    SolarCharger,
    VEBus,
    detect_device_type,
)

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VICTRON_IDENTIFIER

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class VictronBluetoothDeviceData(BluetoothData):
    """Class to hold Victron BLE device data."""

    def __init__(self, advertisement_key: str | None = None) -> None:
        """Initialize the Victron Bluetooth device data with an encryption key."""
        super().__init__()
        self._advertisement_key: str | None = advertisement_key
        self._parser: DeviceData | None = None

    def validate_advertisement_key(self, data: bytes) -> bool:
        """Validate the advertisement key."""
        if not self._advertisement_key:
            _LOGGER.debug("Advertisement key not set")
            return False

        encrypted_data = detect_device_type(data).PARSER.parse(data).encrypted_data

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
            parser = detect_device_type(raw_data)
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
            self._parser = parser(self._advertisement_key)

        data = self._parser.parse(raw_data)
        if isinstance(self._parser, BatteryMonitor):
            self._update_battery_monitor(data)
        elif isinstance(self._parser, DcEnergyMeter):
            self._update_dc_energy_meter(data)
        elif isinstance(self._parser, SolarCharger):
            self._update_solar_charger(data)
        elif isinstance(self._parser, VEBus):
            self._update_vebus(data)

    def _update_battery_monitor(self, data: DeviceData) -> None:
        self.update_sensor(
            "Remaining Minutes",
            Units.TIME_MINUTES,
            data.get_remaining_mins(),
            DeviceClass.DURATION,
        )
        self.update_sensor(
            "Battery Current",
            Units.ELECTRIC_CURRENT_AMPERE,
            data.get_current(),
            DeviceClass.CURRENT,
        )
        self.update_sensor(
            "Battery Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_voltage(),
            DeviceClass.VOLTAGE,
        )
        self.update_sensor(
            "Battery State of Charge",
            Units.PERCENTAGE,
            data.get_soc(),
            DeviceClass.BATTERY,
        )
        self.update_sensor(
            "Consumed Amp Hours",
            None,
            data.get_consumed_ah(),
        )
        self.update_sensor(
            "Battery Monitor Alarm",
            None,
            data.get_alarm(),
        )
        self.update_sensor(
            "Aux Mode",
            None,
            data.get_aux_mode(),
        )
        self.update_sensor(
            "Battery Temperature",
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

    def _update_dc_energy_meter(self, data: DeviceData) -> None:
        self.update_sensor(
            "Meter Type",
            None,
            data.get_meter_type(),
        )
        self.update_sensor(
            "Meter Current",
            Units.ELECTRIC_CURRENT_AMPERE,
            data.get_current(),
            DeviceClass.CURRENT,
        )
        self.update_sensor(
            "Meter Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_voltage(),
            DeviceClass.VOLTAGE,
        )
        self.update_sensor(
            "Meter Alarm",
            None,
            data.get_alarm(),
        )
        self.update_sensor(
            "Meter Temperature",
            Units.TEMP_CELSIUS,
            data.get_temperature(),
            DeviceClass.TEMPERATURE,
        )
        self.update_sensor(
            "Meter Aux Mode",
            None,
            data.get_aux_mode(),
        )
        self.update_sensor(
            "Meter Temperature",
            Units.TEMP_CELSIUS,
            data.get_temperature(),
            DeviceClass.TEMPERATURE,
        )
        self.update_sensor(
            "Meter Secondary Voltage",
            Units.ELECTRIC_POTENTIAL_VOLT,
            data.get_starter_voltage(),
            DeviceClass.VOLTAGE,
        )

    def _update_solar_charger(self, data: DeviceData) -> None:
        self.update_sensor(
            "Charge State",
            None,
            data.get_charge_state(),
        )
        self.update_sensor(
            "Battery Voltage",
            Units.POWER_WATT,
            data.get_battery_voltage(),
            DeviceClass.BATTERY,
        )
        self.update_sensor(
            "Charging Current",
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
            "Solar Power",
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

    def _update_vebus(self, data: DeviceData) -> None:
        self.update_sensor(
            "Device State",
            None,
            data.get_device_state(),
        )
        self.update_sensor(
            "AC In State",
            None,
            data.get_ac_in_state(),
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
            "Battery State of Charge",
            Units.PERCENTAGE,
            data.get_soc(),
            DeviceClass.BATTERY,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    key = entry.data[CONF_API_KEY]
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # remove this device from the scanner
        address: str = entry.data[CONF_ADDRESS]
        hass.data[DOMAIN].scanner.remove_device(address)

        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
