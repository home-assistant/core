"""Expose BM2 protocol readings as Home Assistant Bluetooth sensor updates."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import override

from bleak import BLEDevice
from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from bmx_ble import BM2Generation, BM2Protocol, BM2Reading
from home_assistant_bluetooth import BluetoothServiceInfo
import numpy as np
from sensor_state_data import SensorDeviceClass, SensorUpdate, Units

from homeassistant.config_entries import ConfigEntry

from .const import (
    BATTERY_STATUS_LIST,
    CONF_BATTERY_TYPE,
    CONF_CUSTOM_BATTERY_CHEMISTRY,
    CONF_CUSTOM_CHARGING_VOLTAGE,
    CONF_CUSTOM_CRITICAL_VOLTAGE,
    CONF_CUSTOM_FLOATING_VOLTAGE,
    CONF_CUSTOM_LOW_VOLTAGE,
    CONF_CUSTOM_NUMPY_VOLTS,
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_MODE,
    DEFAULT_BATTERY_TYPE,
    DEFAULT_CUSTOM_BATTERY_CHEMISTRY,
    DEFAULT_CUSTOM_CHARGING_VOLTAGE,
    DEFAULT_CUSTOM_CRITICAL_VOLTAGE,
    DEFAULT_CUSTOM_FLOATING_VOLTAGE,
    DEFAULT_CUSTOM_LOW_VOLTAGE,
    DEFAULT_CUSTOM_NUMPY_VOLTS,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RATE_LIMIT_MODE,
)

_LOGGER = logging.getLogger(__name__)


class Battery(StrEnum):
    """Pre-defined battery chemistries."""

    automatic = "automatic"
    agm = "agm"
    deepcycle = "deepcycle"
    leadacid = "leadacid"
    lifepo4 = "lifepo4"
    lithiumion = "lithiumion"
    itech120x = "itech120x"
    custom = "custom"


@dataclass
class BatteryDetail:
    """Battery chemistry characteristics."""

    battery_chemistry: str
    volts_to_percent: list[float]
    critical_voltage: float
    low_voltage: float
    floating_voltage: float
    charging_voltage: float


BATTERIES = {
    Battery.automatic: BatteryDetail(
        "Automatic",
        [],
        0.0,
        0.0,
        0.0,
        0.0,
    ),
    Battery.agm: BatteryDetail(
        "AGM",
        [
            10.5,
            11.51,
            11.66,
            11.81,
            11.95,
            12.05,
            12.15,
            12.3,
            12.5,
            12.75,
            12.85,
        ],
        11.66,
        11.81,
        13.2,
        14.2,
    ),
    Battery.deepcycle: BatteryDetail(
        "Deep-cycle",
        [10.5, 11.51, 11.66, 11.81, 11.95, 12.05, 12.15, 12.3, 12.5, 12.75, 12.8],
        11.66,
        12.05,
        13.6,
        14.4,
    ),
    Battery.leadacid: BatteryDetail(
        "Lead-acid",
        [10.5, 11.31, 11.58, 11.75, 11.9, 12.06, 12.2, 12.32, 12.42, 12.5, 12.7],
        12.06,
        12.2,
        13.7,
        14.5,
    ),
    Battery.lifepo4: BatteryDetail(
        "LiFePO4",
        [10.0, 12.0, 12.5, 12.8, 12.9, 13.0, 13.1, 13.2, 13.3, 13.4, 13.6],
        10.5,
        12.0,
        13.5,
        14.4,
    ),
    Battery.lithiumion: BatteryDetail(
        "Lithium-ion",
        [10.0, 12.0, 12.8, 12.9, 13.0, 13.05, 13.1, 13.2, 13.3, 13.4, 13.6],
        10.5,
        12.0,
        13.5,
        14.25,
    ),
    Battery.itech120x: BatteryDetail(
        "iTechworld 120X (LiFePO4)",
        [9.5, 10.5, 12.5, 12.7, 12.8, 12.89, 12.91, 12.99, 13.01, 13.1, 13.5],
        10.5,
        12.5,
        13.5,
        14.35,
    ),
    Battery.custom: BatteryDetail(
        "Custom",
        [10.5, 11.58, 12.06, 13.6],
        12.06,
        12.2,
        13.7,
        14.5,
    ),
}


CHEMISTRY_OPTION_TO_BATTERY = {
    "Automatic": Battery.automatic,
    "AGM": Battery.agm,
    "Deep-cycle": Battery.deepcycle,
    "Lead-acid": Battery.leadacid,
    "LiFePO4": Battery.lifepo4,
    "LifePO4": Battery.lifepo4,
    "Lithium-ion": Battery.lithiumion,
    "iTechworld 120X (LiFePO4)": Battery.itech120x,
    "itech120x": Battery.itech120x,
    "Custom": Battery.custom,
}


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

        # Decide if we should process this advertisement and update the sensors
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

        # We're rate-limiting... check to see if sufficient time has passed since the last update
        rate_limit = self.entry.options.get(
            CONF_RATE_LIMIT,
            DEFAULT_RATE_LIMIT,
        )

        # Keep the existing coordinator semantics used by the integration.
        poll_needed = last_poll > rate_limit

        _LOGGER.debug(
            "Poll rate limited for %s: rate_limit=%s, last_poll=%s, poll_needed=%s",
            service_info.address,
            rate_limit,
            last_poll,
            poll_needed,
        )
        return poll_needed

    def _battery_detail(self) -> tuple[BatteryDetail, bool]:
        """Return configured battery chemistry details and custom flag."""
        battery_option = self.entry.options.get(
            CONF_BATTERY_TYPE,
            DEFAULT_BATTERY_TYPE,
        )

        if battery_option == "Automatic (via BM2)":
            return BATTERIES[Battery.automatic], False

        if battery_option != "Custom":
            battery_chemistry = CHEMISTRY_OPTION_TO_BATTERY[battery_option]
            return BATTERIES[battery_chemistry], False

        # Create a fresh BatteryDetail rather than mutating the shared
        # BATTERIES[Battery.custom] object.
        battery_detail = BatteryDetail(
            battery_chemistry=self.entry.options.get(
                CONF_CUSTOM_BATTERY_CHEMISTRY,
                DEFAULT_CUSTOM_BATTERY_CHEMISTRY,
            ),
            volts_to_percent=self.entry.options.get(
                CONF_CUSTOM_NUMPY_VOLTS,
                DEFAULT_CUSTOM_NUMPY_VOLTS,
            ),
            critical_voltage=self.entry.options.get(
                CONF_CUSTOM_CRITICAL_VOLTAGE,
                DEFAULT_CUSTOM_CRITICAL_VOLTAGE,
            ),
            low_voltage=self.entry.options.get(
                CONF_CUSTOM_LOW_VOLTAGE,
                DEFAULT_CUSTOM_LOW_VOLTAGE,
            ),
            floating_voltage=self.entry.options.get(
                CONF_CUSTOM_FLOATING_VOLTAGE,
                DEFAULT_CUSTOM_FLOATING_VOLTAGE,
            ),
            charging_voltage=self.entry.options.get(
                CONF_CUSTOM_CHARGING_VOLTAGE,
                DEFAULT_CUSTOM_CHARGING_VOLTAGE,
            ),
        )
        return battery_detail, True

    def _apply_reading(self, reading: BM2Reading) -> None:
        """Apply available fields and publish a decoded reading.

        Advertisement fallback can be partial.  Legacy advertisements carry
        percentage but no voltage/status, so unavailable fields are deliberately
        left at their previous Home Assistant values.
        """
        voltage = reading.voltage
        percentage = reading.percentage
        status = reading.status

        battery_detail, custom = self._battery_detail()

        # Chemistry-based percentage/status calculations require voltage.
        if battery_detail is not None:
            self.update_sensor(
                key="battery_chemistry",
                native_value=battery_detail.battery_chemistry,
                native_unit_of_measurement=None,
            )

        if (
            voltage is not None
            and percentage is not None
            and battery_detail.battery_chemistry != "Automatic"
        ):
            # Adjust the percentage based on the defined battery chemistry
            percentage = self._adjust_percentage(
                percentage,
                battery_detail,
                voltage,
                custom,
            )

            # We can't revise the status without voltage information
            status = self._adjust_status(
                status if status is not None else 2,
                battery_detail,
                voltage,
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
            status_text = BATTERY_STATUS_LIST.get(status, "unknown")
            self.update_sensor(
                key="battery_status",
                native_unit_of_measurement=None,
                native_value=status_text,
                device_class=None,
            )
            self._charging = status >= 4

        # Generation is inferred from advertisements.  Publish it alongside
        # either an active or fallback update once it is known.
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

    async def async_poll(self, ble_device: BLEDevice | None) -> SensorUpdate:
        """Publish an active reading or the cached advertisement fallback."""
        reading = await BM2Protocol.async_poll(self, ble_device)
        self._apply_reading(reading)
        return self._finish_update()

    def _adjust_percentage(
        self,
        raw_percentage: int,
        battery_detail: BatteryDetail,
        voltage: float,
        custom: bool = False,
    ) -> int:
        """Adjust battery percentage using the configured chemistry curve."""
        if not custom:
            np_percent = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        else:
            np_percent = [0, 20, 50, 100]

        new_percentage = int(
            np.interp(
                voltage,
                battery_detail.volts_to_percent,
                np_percent,
            )
        )

        _LOGGER.debug(
            "Adjusting percentage based on battery chemistry %s: "
            "voltage=%s, raw=%s, adjusted=%s",
            battery_detail.battery_chemistry,
            voltage,
            raw_percentage,
            new_percentage,
        )
        return new_percentage

    def _adjust_status(
        self,
        raw_status: int,
        battery_detail: BatteryDetail,
        voltage: float,
    ) -> int:
        """Adjust battery status using the configured chemistry thresholds."""
        if voltage >= battery_detail.charging_voltage:
            new_status = 4  # Charging
        elif voltage >= battery_detail.floating_voltage:
            new_status = 8  # Floating
        elif voltage <= battery_detail.critical_voltage:
            new_status = 0  # Critical
        elif voltage <= battery_detail.low_voltage:
            new_status = 1  # Low
        else:
            new_status = 2  # Normal

        _LOGGER.debug(
            "Adjusting state based on battery chemistry %s: "
            "critical=%s, low=%s, float=%s, charging=%s, voltage=%s, "
            "raw=%s, adjusted=%s",
            battery_detail.battery_chemistry,
            battery_detail.critical_voltage,
            battery_detail.low_voltage,
            battery_detail.floating_voltage,
            battery_detail.charging_voltage,
            voltage,
            raw_status,
            new_status,
        )
        return new_status
