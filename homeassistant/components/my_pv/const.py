"""Constants for the my-PV integration."""

from typing import Final

from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

DOMAIN: Final = "my_pv"

CONF_TYPE_LOCAL: Final = "local"
CONF_TYPE_CLOUD: Final = "cloud"

CONF_SERIAL_NUMBER: Final = "serial_number"

UPDATE_COMMANDS = [
    "check_fwupd",
    "co_fw",
    "firmware_update",
    "force_psupdate",
    "p9s_fw",
    "ps_fw",
]
RESERVED_KEYS = [
    "check_fwupd",
    "coversion",  # codespell:ignore coversion
    "coversionlatest",
    "devmode",
    "firmware_download",
    "firmware_update",
    "fwversion",
    "fwversionlatest",
    "p9s_fw",
    "ps_fw",
    "psversion",
    "psversionlatest",
    "upd_percentage",
    "upd_state",
    "ww1target",
]

BUTTON_DEVICE_CLASSES: Final = {"reboot_device": ButtonDeviceClass.RESTART}

NUMBER_DEVICE_CLASSES: Final = {
    "ww_boost_h": NumberDeviceClass.TEMPERATURE,
    "ww_targ_h": NumberDeviceClass.TEMPERATURE,
    "ww1boost": NumberDeviceClass.TEMPERATURE,
    "ww1target": NumberDeviceClass.TEMPERATURE,
}

SENSOR_DEVICE_CLASSES: Final = {
    "curr_l2": SensorDeviceClass.CURRENT,
    "curr_l3": SensorDeviceClass.CURRENT,
    "curr_mains": SensorDeviceClass.CURRENT,
    "freq": SensorDeviceClass.FREQUENCY,
    "power": SensorDeviceClass.POWER,
    "power_ac9": SensorDeviceClass.POWER,
    "power_act": SensorDeviceClass.POWER,
    "power_elwa2": SensorDeviceClass.POWER,
    "power_grid": SensorDeviceClass.POWER,
    "soc": SensorDeviceClass.BATTERY,
    "temp1": SensorDeviceClass.TEMPERATURE,
    "temp2": SensorDeviceClass.TEMPERATURE,
    "temp3": SensorDeviceClass.TEMPERATURE,
    "temp4": SensorDeviceClass.TEMPERATURE,
    "uptime": SensorDeviceClass.DURATION,
    "volt_l2": SensorDeviceClass.VOLTAGE,
    "volt_l3": SensorDeviceClass.VOLTAGE,
    "volt_mains": SensorDeviceClass.VOLTAGE,
    "wifi_signal": SensorDeviceClass.SIGNAL_STRENGTH,
    "wifi_signal_strength": SensorDeviceClass.SIGNAL_STRENGTH,
}

SENSOR_STATE_CLASSES: Final = {
    "uptime": SensorStateClass.TOTAL_INCREASING,
}

ENTITY_CATEGORIES: Final = {
    "cur_eth_mode": EntityCategory.DIAGNOSTIC,
    "freq": EntityCategory.DIAGNOSTIC,
    "reboot_device": EntityCategory.DIAGNOSTIC,
    "uptime": EntityCategory.DIAGNOSTIC,
    "volt_l2": EntityCategory.DIAGNOSTIC,
    "volt_l3": EntityCategory.DIAGNOSTIC,
    "volt_mains": EntityCategory.DIAGNOSTIC,
    "wifi_signal": EntityCategory.DIAGNOSTIC,
    "wifi_signal_strength": EntityCategory.DIAGNOSTIC,
}
