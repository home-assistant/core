"""Common helpers for gree test cases."""
from unittest.mock import AsyncMock, Mock


def build_device_info_mock(
    name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
):
    """Build mock device info structure."""
    mock = Mock(ip=ipAddress, port=7000, mac=mac)
    mock.name = name
    return mock


def build_device_mock(name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"):
    """Build mock device object."""
    mock = Mock(
        device_info=build_device_info_mock(name, ipAddress, mac),
        name=name,
        bind=AsyncMock(),
        update_state=AsyncMock(),
        push_state_update=AsyncMock(),
        temperature_units=0,
        mode=0,
        fan_speed=0,
        horizontal_swing=0,
        vertical_swing=0,
        target_temperature=25,
        power=False,
        sleep=False,
        quiet=False,
        turbo=False,
        power_save=False,
        steady_heat=False,
    )
    return mock
