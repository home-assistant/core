"""Constants for the Imou tests."""

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
    PARAM_STATE,
    PARAM_STATUS,
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
    device._sensors[PARAM_STATUS] = {PARAM_STATE: status.value}
    if switches:
        device._switches.update(switches)
    if sensors:
        device._sensors.update(sensors)
    return device


DEFAULT_MOCK_DEVICES = [
    create_online_device(
        "d1",
        "Device 1",
        button_keys=(PARAM_MUTE, PARAM_PTZ_UP, PARAM_RESTART_DEVICE),
    ),
]
