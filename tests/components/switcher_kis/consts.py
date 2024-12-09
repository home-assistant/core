"""Constants for the Switcher integration tests."""

from aioswitcher.device import (
    DeviceState,
    DeviceType,
    ShutterChildLock,
    ShutterDirection,
    SwitcherDualShutterSingleLight,
    SwitcherLight,
    SwitcherPowerPlug,
    SwitcherShutter,
    SwitcherSingleShutterDualLight,
    SwitcherThermostat,
    SwitcherWaterHeater,
    ThermostatFanLevel,
    ThermostatMode,
    ThermostatSwing,
)

DUMMY_AUTO_OFF_SET = "01:30:00"
DUMMY_AUTO_SHUT_DOWN = "02:00:00"
DUMMY_DEVICE_ID1 = "a123bc"
DUMMY_DEVICE_ID2 = "cafe12"
DUMMY_DEVICE_ID3 = "bada77"
DUMMY_DEVICE_ID4 = "bbd164"
DUMMY_DEVICE_ID5 = "bcdb64"
DUMMY_DEVICE_ID6 = "bcdc64"
DUMMY_DEVICE_ID7 = "bcdd64"
DUMMY_DEVICE_ID8 = "bcde64"
DUMMY_DEVICE_ID9 = "bcdf64"
DUMMY_DEVICE_KEY1 = "18"
DUMMY_DEVICE_KEY2 = "01"
DUMMY_DEVICE_KEY3 = "12"
DUMMY_DEVICE_KEY4 = "07"
DUMMY_DEVICE_KEY5 = "15"
DUMMY_DEVICE_KEY6 = "16"
DUMMY_DEVICE_KEY7 = "17"
DUMMY_DEVICE_KEY8 = "18"
DUMMY_DEVICE_KEY9 = "19"
DUMMY_DEVICE_NAME1 = "Plug 23BC"
DUMMY_DEVICE_NAME2 = "Heater FE12"
DUMMY_DEVICE_NAME3 = "Breeze AB39"
DUMMY_DEVICE_NAME4 = "Runner DD77"
DUMMY_DEVICE_NAME5 = "RunnerS11 6CF5"
DUMMY_DEVICE_NAME6 = "RunnerS12 A9BE"
DUMMY_DEVICE_NAME7 = "Light 36BB"
DUMMY_DEVICE_NAME8 = "Light 36CB"
DUMMY_DEVICE_NAME9 = "Light 36DB"
DUMMY_DEVICE_PASSWORD = "12345678"
DUMMY_ELECTRIC_CURRENT1 = 0.5
DUMMY_ELECTRIC_CURRENT2 = 12.8
DUMMY_IP_ADDRESS1 = "192.168.100.157"
DUMMY_IP_ADDRESS2 = "192.168.100.158"
DUMMY_IP_ADDRESS3 = "192.168.100.159"
DUMMY_IP_ADDRESS4 = "192.168.100.160"
DUMMY_IP_ADDRESS5 = "192.168.100.161"
DUMMY_IP_ADDRESS6 = "192.168.100.162"
DUMMY_IP_ADDRESS7 = "192.168.100.163"
DUMMY_IP_ADDRESS8 = "192.168.100.164"
DUMMY_IP_ADDRESS9 = "192.168.100.165"
DUMMY_MAC_ADDRESS1 = "A1:B2:C3:45:67:D8"
DUMMY_MAC_ADDRESS2 = "A1:B2:C3:45:67:D9"
DUMMY_MAC_ADDRESS3 = "A1:B2:C3:45:67:DA"
DUMMY_MAC_ADDRESS4 = "A1:B2:C3:45:67:DB"
DUMMY_MAC_ADDRESS5 = "A1:B2:C3:45:67:DC"
DUMMY_MAC_ADDRESS6 = "A1:B2:C3:45:67:DD"
DUMMY_MAC_ADDRESS7 = "A1:B2:C3:45:67:DE"
DUMMY_MAC_ADDRESS8 = "A1:B2:C3:45:67:DF"
DUMMY_MAC_ADDRESS9 = "A1:B2:C3:45:67:DG"
DUMMY_TOKEN_NEEDED1 = False
DUMMY_TOKEN_NEEDED2 = False
DUMMY_TOKEN_NEEDED3 = False
DUMMY_TOKEN_NEEDED4 = False
DUMMY_TOKEN_NEEDED5 = True
DUMMY_TOKEN_NEEDED6 = True
DUMMY_TOKEN_NEEDED7 = True
DUMMY_TOKEN_NEEDED8 = True
DUMMY_TOKEN_NEEDED9 = True
DUMMY_PHONE_ID = "1234"
DUMMY_POWER_CONSUMPTION1 = 100
DUMMY_POWER_CONSUMPTION2 = 2780
DUMMY_REMAINING_TIME = "01:29:32"
DUMMY_TIMER_MINUTES_SET = "90"
DUMMY_THERMOSTAT_MODE = ThermostatMode.COOL
DUMMY_TEMPERATURE = 24.1
DUMMY_TARGET_TEMPERATURE = 23
DUMMY_FAN_LEVEL = ThermostatFanLevel.LOW
DUMMY_SWING = ThermostatSwing.OFF
DUMMY_REMOTE_ID = "ELEC7001"
DUMMY_POSITION = [54]
DUMMY_POSITION_2 = [54, 54]
DUMMY_DIRECTION = [ShutterDirection.SHUTTER_STOP]
DUMMY_DIRECTION_2 = [ShutterDirection.SHUTTER_STOP, ShutterDirection.SHUTTER_STOP]
DUMMY_CHILD_LOCK = [ShutterChildLock.OFF]
DUMMY_CHILD_LOCK_2 = [ShutterChildLock.OFF, ShutterChildLock.OFF]
DUMMY_USERNAME = "email"
DUMMY_TOKEN = "zvVvd7JxtN7CgvkD1Psujw=="
DUMMY_LIGHT = [DeviceState.ON]
DUMMY_LIGHT_2 = [DeviceState.ON, DeviceState.ON]
DUMMY_LIGHT_3 = [DeviceState.ON, DeviceState.ON, DeviceState.ON]

DUMMY_PLUG_DEVICE = SwitcherPowerPlug(
    DeviceType.POWER_PLUG,
    DeviceState.ON,
    DUMMY_DEVICE_ID1,
    DUMMY_DEVICE_KEY1,
    DUMMY_IP_ADDRESS1,
    DUMMY_MAC_ADDRESS1,
    DUMMY_DEVICE_NAME1,
    DUMMY_TOKEN_NEEDED1,
    DUMMY_POWER_CONSUMPTION1,
    DUMMY_ELECTRIC_CURRENT1,
)

DUMMY_WATER_HEATER_DEVICE = SwitcherWaterHeater(
    DeviceType.V4,
    DeviceState.ON,
    DUMMY_DEVICE_ID2,
    DUMMY_DEVICE_KEY2,
    DUMMY_IP_ADDRESS2,
    DUMMY_MAC_ADDRESS2,
    DUMMY_DEVICE_NAME2,
    DUMMY_TOKEN_NEEDED2,
    DUMMY_POWER_CONSUMPTION2,
    DUMMY_ELECTRIC_CURRENT2,
    DUMMY_REMAINING_TIME,
    DUMMY_AUTO_SHUT_DOWN,
)

DUMMY_SHUTTER_DEVICE = SwitcherShutter(
    DeviceType.RUNNER,
    DeviceState.ON,
    DUMMY_DEVICE_ID4,
    DUMMY_DEVICE_KEY4,
    DUMMY_IP_ADDRESS4,
    DUMMY_MAC_ADDRESS4,
    DUMMY_DEVICE_NAME4,
    DUMMY_TOKEN_NEEDED4,
    DUMMY_POSITION,
    DUMMY_DIRECTION,
    DUMMY_CHILD_LOCK,
)

DUMMY_SINGLE_SHUTTER_DUAL_LIGHT_DEVICE = SwitcherSingleShutterDualLight(
    DeviceType.RUNNER_S11,
    DeviceState.ON,
    DUMMY_DEVICE_ID5,
    DUMMY_DEVICE_KEY5,
    DUMMY_IP_ADDRESS5,
    DUMMY_MAC_ADDRESS5,
    DUMMY_DEVICE_NAME5,
    DUMMY_TOKEN_NEEDED5,
    DUMMY_POSITION,
    DUMMY_DIRECTION,
    DUMMY_CHILD_LOCK,
    DUMMY_LIGHT_2,
)

DUMMY_DUAL_SHUTTER_SINGLE_LIGHT_DEVICE = SwitcherDualShutterSingleLight(
    DeviceType.RUNNER_S12,
    DeviceState.ON,
    DUMMY_DEVICE_ID6,
    DUMMY_DEVICE_KEY6,
    DUMMY_IP_ADDRESS6,
    DUMMY_MAC_ADDRESS6,
    DUMMY_DEVICE_NAME6,
    DUMMY_TOKEN_NEEDED6,
    DUMMY_POSITION_2,
    DUMMY_DIRECTION_2,
    DUMMY_CHILD_LOCK_2,
    DUMMY_LIGHT,
)

DUMMY_THERMOSTAT_DEVICE = SwitcherThermostat(
    DeviceType.BREEZE,
    DeviceState.ON,
    DUMMY_DEVICE_ID3,
    DUMMY_DEVICE_KEY3,
    DUMMY_IP_ADDRESS3,
    DUMMY_MAC_ADDRESS3,
    DUMMY_DEVICE_NAME3,
    DUMMY_TOKEN_NEEDED3,
    DUMMY_THERMOSTAT_MODE,
    DUMMY_TEMPERATURE,
    DUMMY_TARGET_TEMPERATURE,
    DUMMY_FAN_LEVEL,
    DUMMY_SWING,
    DUMMY_REMOTE_ID,
)

DUMMY_LIGHT_DEVICE = SwitcherLight(
    DeviceType.LIGHT_SL01,
    DeviceState.ON,
    DUMMY_DEVICE_ID7,
    DUMMY_DEVICE_KEY7,
    DUMMY_IP_ADDRESS7,
    DUMMY_MAC_ADDRESS7,
    DUMMY_DEVICE_NAME7,
    DUMMY_TOKEN_NEEDED7,
    DUMMY_LIGHT,
)

DUMMY_DUAL_LIGHT_DEVICE = SwitcherLight(
    DeviceType.LIGHT_SL02,
    DeviceState.ON,
    DUMMY_DEVICE_ID8,
    DUMMY_DEVICE_KEY8,
    DUMMY_IP_ADDRESS8,
    DUMMY_MAC_ADDRESS8,
    DUMMY_DEVICE_NAME8,
    DUMMY_TOKEN_NEEDED8,
    DUMMY_LIGHT_2,
)

DUMMY_TRIPLE_LIGHT_DEVICE = SwitcherLight(
    DeviceType.LIGHT_SL03,
    DeviceState.ON,
    DUMMY_DEVICE_ID9,
    DUMMY_DEVICE_KEY9,
    DUMMY_IP_ADDRESS9,
    DUMMY_MAC_ADDRESS9,
    DUMMY_DEVICE_NAME9,
    DUMMY_TOKEN_NEEDED9,
    DUMMY_LIGHT_3,
)

DUMMY_SWITCHER_DEVICES = [DUMMY_PLUG_DEVICE, DUMMY_WATER_HEATER_DEVICE]

DUMMY_SWITCHER_SENSORS_DEVICES = [
    DUMMY_PLUG_DEVICE,
    DUMMY_WATER_HEATER_DEVICE,
    DUMMY_THERMOSTAT_DEVICE,
]
