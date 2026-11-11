"""Expose BM2 protocol readings as Home Assistant Bluetooth sensor updates."""

import logging
from typing import override

from bleak import BLEDevice
from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from bmx_ble import BM2Generation, BM2Protocol, BM2Reading
from bmx_ble.battery import (
    Battery,
    BatteryProfile,
    BatteryStatus,
    custom_battery_profile,
    get_battery_profile,
    interpret_reading,
    needs_active_read,
)
from habluetooth import BluetoothServiceInfoBleak
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorDeviceClass, SensorUpdate, Units

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_BATTERY_TYPE,
    CONF_CUSTOM_BATTERY_CHEMISTRY,
    CONF_CUSTOM_CHARGING_VOLTAGE,
    CONF_CUSTOM_CRITICAL_VOLTAGE,
    CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE,
    CONF_CUSTOM_FLOATING_VOLTAGE,
    CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
    CONF_CUSTOM_LOW_VOLTAGE,
    CONF_CUSTOM_NUMPY_VOLTS,
    DEFAULT_BATTERY_TYPE,
    DEFAULT_CUSTOM_BATTERY_CHEMISTRY,
    DEFAULT_CUSTOM_CHARGING_VOLTAGE,
    DEFAULT_CUSTOM_CRITICAL_VOLTAGE,
    DEFAULT_CUSTOM_FIFTY_PERCENT_VOLTAGE,
    DEFAULT_CUSTOM_FLOATING_VOLTAGE,
    DEFAULT_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
    DEFAULT_CUSTOM_LOW_VOLTAGE,
)

_LOGGER = logging.getLogger(__name__)

# Seconds between GATT connections; advertisements trigger them, never a timer.
MIN_POLL_INTERVAL = 30


class BMxBluetoothDeviceData(BM2Protocol, BluetoothData):
    """Data for BMx BLE sensors."""

    def __init__(self) -> None:
        """Initialise a device."""
        BluetoothData.__init__(self)
        BM2Protocol.__init__(self)

        # Populated by __init__.py immediately after construction.
        self.entry: ConfigEntry

    @override
    def _start_update(self, data: BluetoothServiceInfo) -> None:
        """Refresh device metadata and publish this advertisement's reading."""
        _LOGGER.debug("New advertisement - %s", data)

        address = data.address

        # Do not require manufacturer ID 0x004C.  That is the Apple iBeacon
        # record and is not the encrypted voltage/SOC telemetry record.
        self.set_device_manufacturer("Shenzhen Leagend Optoelectronics")

        device_type = "BM2 battery monitor"
        self.set_device_type(device_type)
        name = f"{device_type} ({short_address(address)})"
        self.set_device_name(name)
        self.set_title(name)

        reading = self.process_advertisement(
            data.manufacturer_data,
            raw=data.raw if isinstance(data, BluetoothServiceInfoBleak) else None,
        )
        if reading is None:
            return
        profile = self._battery_profile()
        # A legacy device's own percentage disagrees with the chosen curve.
        if reading.generation is BM2Generation.LEGACY and profile.volts_to_percent:
            return
        self._apply_reading(reading, profile)

    def poll_needed(
        self,
        service_info: BluetoothServiceInfo,
        last_poll: float | None,
    ) -> bool:
        """Return whether to connect for data the advertisement cannot provide.

        last_poll is the number of seconds since the previous poll.
        """
        # A poll is running; the debouncer would otherwise queue a duplicate.
        if self.ignore_advertisement:
            return False
        if not needs_active_read(self.bm2_generation, self._battery_profile()):
            return False
        return last_poll is None or last_poll >= MIN_POLL_INTERVAL

    def _battery_profile(self) -> BatteryProfile:
        """Map entry options to a library battery profile."""
        options = self.entry.options
        chemistry = Battery(options.get(CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE))
        if chemistry is not Battery.custom:
            return get_battery_profile(chemistry)

        # Keep accepting the historical derived lookup key. New profiles use
        # individual threshold options, with the lookup as a fallback only.
        volts = options.get(
            CONF_CUSTOM_NUMPY_VOLTS,
            [
                DEFAULT_CUSTOM_CRITICAL_VOLTAGE,
                DEFAULT_CUSTOM_LOW_VOLTAGE,
                DEFAULT_CUSTOM_FIFTY_PERCENT_VOLTAGE,
                DEFAULT_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
            ],
        )
        return custom_battery_profile(
            battery_chemistry=options.get(
                CONF_CUSTOM_BATTERY_CHEMISTRY, DEFAULT_CUSTOM_BATTERY_CHEMISTRY
            ),
            critical_voltage=options.get(CONF_CUSTOM_CRITICAL_VOLTAGE, volts[0]),
            low_voltage=options.get(CONF_CUSTOM_LOW_VOLTAGE, volts[1]),
            fifty_percent_voltage=options.get(
                CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE, volts[2]
            ),
            hundred_percent_voltage=options.get(
                CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE, volts[3]
            ),
            floating_voltage=options.get(
                CONF_CUSTOM_FLOATING_VOLTAGE, DEFAULT_CUSTOM_FLOATING_VOLTAGE
            ),
            charging_voltage=options.get(
                CONF_CUSTOM_CHARGING_VOLTAGE, DEFAULT_CUSTOM_CHARGING_VOLTAGE
            ),
        )

    def _apply_reading(self, reading: BM2Reading, profile: BatteryProfile) -> None:
        """Publish the fields a reading carries.

        Advertisements are partial, so missing fields keep their previous
        Home Assistant values.
        """
        interpreted = interpret_reading(reading, profile)
        voltage = interpreted.voltage
        percentage = interpreted.percentage
        status = interpreted.status

        self.update_sensor(
            key="battery_chemistry",
            native_value=interpreted.battery_chemistry,
            native_unit_of_measurement=None,
        )

        if percentage is not None:
            self.update_sensor(
                key="battery_percent",
                native_unit_of_measurement=Units.PERCENTAGE,
                native_value=percentage,
                device_class=SensorDeviceClass.BATTERY,
            )

        if voltage is not None:
            self.update_sensor(
                key="battery_voltage",
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=voltage,
                device_class=SensorDeviceClass.VOLTAGE,
            )

        if status is not None:
            self.update_sensor(
                key="battery_status",
                native_unit_of_measurement=None,
                # An unrecognised status code is reported as unknown.
                native_value=(
                    None if status is BatteryStatus.unknown else status.value
                ),
                device_class=None,
            )

        if self._bm2_generation is not BM2Generation.UNKNOWN:
            self.update_sensor(
                key="bm2_generation",
                native_unit_of_measurement=None,
                native_value=str(self._bm2_generation),
                device_class=None,
            )

        _LOGGER.debug(
            "Published BM2 %s reading: generation=%s, voltage=%s, "
            "percentage=%s, status=%s",
            reading.source,
            self._bm2_generation,
            voltage,
            percentage,
            status,
        )

    async def async_poll_sensors(self, ble_device: BLEDevice) -> SensorUpdate:
        """Read the BM2 over GATT and publish the result."""
        reading = await self.async_poll(ble_device)
        self._apply_reading(reading, self._battery_profile())
        return self._finish_update()
