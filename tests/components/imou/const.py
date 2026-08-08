"""Constants for the Imou tests."""

from pyimouapi.const import (
    PARAM_BATTERY,
    PARAM_STATE,
    PARAM_STATE_VARIANT,
    PARAM_STATUS,
    PARAM_STORAGE_USED,
    STATE_VARIANT_ENUM,
    STATE_VARIANT_NUMERIC,
)
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.components.imou.button import (
    PARAM_MUTE,
    PARAM_PTZ_UP,
    PARAM_RESTART_DEVICE,
)
from homeassistant.components.imou.const import (
    CONF_API_URL,
    CONF_APP_ID,
    CONF_APP_SECRET,
    PARAM_HEADER_DETECT,
    PARAM_LIGHT,
    PARAM_MOTION_DETECT,
    PARAM_PLUG_SWITCH,
)

TEST_APP_ID = "test_app_id"
TEST_APP_SECRET = "test_app_secret"
TEST_API_URL = "sg"

USER_INPUT = {
    CONF_APP_ID: TEST_APP_ID,
    CONF_APP_SECRET: TEST_APP_SECRET,
    CONF_API_URL: TEST_API_URL,
}

CONFIG_ENTRY_DATA = {
    CONF_APP_ID: TEST_APP_ID,
    CONF_APP_SECRET: TEST_APP_SECRET,
    CONF_API_URL: TEST_API_URL,
}

UNKNOWN_BUTTON_KEY = "legacy_unknown_button"
UNKNOWN_SWITCH_KEY = "legacy_unknown_switch"
UNKNOWN_SENSOR_KEY = "legacy_unknown_sensor"

DEFAULT_SWITCHES = {
    PARAM_MOTION_DETECT: {PARAM_STATE: False},
    PARAM_HEADER_DETECT: {PARAM_STATE: True},
    PARAM_LIGHT: {PARAM_STATE: False},
    PARAM_PLUG_SWITCH: {PARAM_STATE: True},
}

DEFAULT_SENSORS = {
    PARAM_STATUS: {PARAM_STATE: "online", PARAM_STATE_VARIANT: STATE_VARIANT_ENUM},
    PARAM_BATTERY: {PARAM_STATE: 85, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    PARAM_STORAGE_USED: {PARAM_STATE: 42, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    "temperature_current": {
        PARAM_STATE: 22.5,
        PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC,
    },
    "humidity_current": {PARAM_STATE: 55.0, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    "power": {PARAM_STATE: 12.3, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    "voltage": {PARAM_STATE: 220.0, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    "current": {PARAM_STATE: 0.5, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    "switch_cnt": {PARAM_STATE: 3, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    "use_electricity": {PARAM_STATE: 1.5, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
    "use_time": {PARAM_STATE: 120, PARAM_STATE_VARIANT: STATE_VARIANT_NUMERIC},
}


def create_online_device(
    device_id: str,
    name: str,
    *,
    channel_id: str | None = None,
    button_keys: tuple[str, ...] = (),
    switches: dict[str, dict] | None = None,
    sensors: dict[str, dict] | None = None,
) -> ImouHaDevice:
    """Build an online ImouHaDevice for tests."""
    return create_device(
        device_id,
        name,
        channel_id=channel_id,
        button_keys=button_keys,
        status=DeviceStatus.ONLINE,
        switches=switches,
        sensors=sensors,
    )


def create_offline_device(
    device_id: str,
    name: str,
    *,
    channel_id: str | None = None,
    button_keys: tuple[str, ...] = (),
) -> ImouHaDevice:
    """Build an offline ImouHaDevice for tests."""
    return create_device(
        device_id,
        name,
        channel_id=channel_id,
        button_keys=button_keys,
        status=DeviceStatus.OFFLINE,
    )


def create_device(
    device_id: str,
    name: str,
    *,
    channel_id: str | None = None,
    button_keys: tuple[str, ...] = (),
    status: DeviceStatus = DeviceStatus.ONLINE,
    switches: dict[str, dict] | None = None,
    sensors: dict[str, dict] | None = None,
) -> ImouHaDevice:
    """Build an ImouHaDevice for tests."""
    device = ImouHaDevice(device_id, name, "Imou", "m1", "1.0")
    if channel_id is not None:
        device.set_channel_id(channel_id)
    for key in button_keys:
        device._buttons[key] = {}
    device._sensors[PARAM_STATUS] = {
        PARAM_STATE: status.value,
        PARAM_STATE_VARIANT: STATE_VARIANT_ENUM,
    }
    if switches:
        device._switches.update({key: dict(value) for key, value in switches.items()})
    if sensors:
        device._sensors.update({key: dict(value) for key, value in sensors.items()})
    return device


def default_mock_devices() -> list[ImouHaDevice]:
    """Return a fresh default device list for tests."""
    return [
        create_online_device(
            "d1",
            "Device 1",
            button_keys=(PARAM_MUTE, PARAM_PTZ_UP, PARAM_RESTART_DEVICE),
        ),
    ]


def sensor_mock_devices() -> list[ImouHaDevice]:
    """Return a fresh sensor-focused device list for tests."""
    return [
        create_online_device(
            "d1",
            "Device 1",
            button_keys=(),
            sensors=DEFAULT_SENSORS,
        ),
    ]
