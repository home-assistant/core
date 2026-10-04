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
    custom_battery_profile,
    get_battery_profile,
    interpret_reading,
)
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
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_MODE,
    DEFAULT_BATTERY_TYPE,
    DEFAULT_CUSTOM_BATTERY_CHEMISTRY,
    DEFAULT_CUSTOM_CHARGING_VOLTAGE,
    DEFAULT_CUSTOM_CRITICAL_VOLTAGE,
    DEFAULT_CUSTOM_FIFTY_PERCENT_VOLTAGE,
    DEFAULT_CUSTOM_FLOATING_VOLTAGE,
    DEFAULT_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
    DEFAULT_CUSTOM_LOW_VOLTAGE,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RATE_LIMIT_MODE,
)

_LOGGER = logging.getLogger(__name__)


class BMxBluetoothDeviceData(BM2Protocol, BluetoothData):
    """Data for BMx BLE sensors."""

    def __init__(self) -> None:
        """Initialise a device."""
        BluetoothData.__init__(self)
        BM2Protocol.__init__(self)

        # If True, the latest interpreted status says the battery is charging
        # or floating.
        self._charging = False

        # Populated by __init__.py immediately after construction.
        self.entry: ConfigEntry

    @override
    def _start_update(self, data: BluetoothServiceInfo) -> None:
        """Process an advertisement.

        Device metadata is refreshed and, where possible, the newer encrypted
        BM2 telemetry frame is decoded and cached.  Sensor values are deliberately
        not published here; the cache is only consumed when the scheduled active
        poll fails (or no connectable Bluetooth path exists).
        """
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

        self.process_advertisement(data.manufacturer_data)

    def poll_needed(
        self,
        service_info: BluetoothServiceInfo,
        last_poll: float | None,
    ) -> bool:
        """Return True when the coordinator should perform its scheduled poll. last_poll is the number of seconds since, well, the last poll!"""

        _LOGGER.debug(
            "Inside 'poll_needed' for %s, _ignore_advertisement=%s, _charging=%s",
            service_info.address,
            self._ignore_advertisement,
            self._charging,
        )

        if self._ignore_advertisement:
            return False

        if last_poll is None:
            return True

        rate_limit_mode = self.entry.options.get(
            CONF_RATE_LIMIT_MODE, DEFAULT_RATE_LIMIT_MODE
        )

        if rate_limit_mode == "never":
            return True

        if (rate_limit_mode == "when_not_charging" and self._charging) or (
            rate_limit_mode == "when_charging" and not self._charging
        ):
            return True

        rate_limit = self.entry.options.get(
            CONF_RATE_LIMIT,
            DEFAULT_RATE_LIMIT,
        )

        poll_needed = last_poll >= rate_limit

        _LOGGER.debug(
            "Poll rate limited for %s: rate_limit=%s, last_poll=%s, poll_needed=%s",
            service_info.address,
            rate_limit,
            last_poll,
            poll_needed,
        )
        return poll_needed

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

    def _apply_reading(self, reading: BM2Reading) -> None:
        """Apply available fields and publish a decoded reading.

        Advertisement fallback can be partial.  Legacy advertisements carry
        percentage but no voltage/status, so unavailable fields are deliberately
        left at their previous Home Assistant values.
        """
        interpreted = interpret_reading(reading, self._battery_profile())
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

        # Automatic-via-BM2 passive packets do not expose a decoded status.
        # Leave the previous status intact instead of inventing one.
        if status is not None:
            self.update_sensor(
                key="battery_status",
                native_unit_of_measurement=None,
                native_value=status,
                device_class=None,
            )
        if interpreted.charging is not None:
            self._charging = interpreted.charging

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

    async def async_poll_sensors(self, ble_device: BLEDevice | None) -> SensorUpdate:
        """Publish an active reading or the cached advertisement fallback."""
        reading = await BM2Protocol.async_poll(self, ble_device)
        self._apply_reading(reading)
        return self._finish_update()
