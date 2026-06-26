"""Tests for the Amcrest integration setup."""

import re
from unittest.mock import MagicMock, patch

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest.const import DATA_AMCREST, DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CAMERA_CONFIG = {
    "amcrest": [
        {
            "host": "192.168.1.100",
            "username": "admin",
            "password": "password",
        }
    ]
}

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class _CheckerOnline:
    """Mock AmcrestChecker — camera online, returns serial SN-LIVE."""

    available = True

    @property
    def async_serial_number(self):
        async def _get() -> str:
            return "SN-LIVE"

        return _get()


class _CheckerEmptySerial:
    """Mock AmcrestChecker — camera online but reports an empty serial number."""

    available = True

    @property
    def async_serial_number(self):
        async def _get() -> str:
            return ""

        return _get()


class _CheckerOffline:
    """Mock AmcrestChecker — camera unreachable, raises AmcrestError on serial fetch."""

    available = True

    @property
    def async_serial_number(self):
        async def _get() -> str:
            raise AmcrestError("Camera offline")

        return _get()


@pytest.mark.usefixtures("mock_event_monitor", "mock_discovery")
async def test_serial_fetched_on_first_setup(
    hass: HomeAssistant,
    mock_store: MagicMock,
) -> None:
    """Serial number is fetched from camera and persisted on first setup."""
    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        return_value=_CheckerOnline(),
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)

    device = hass.data[DATA_AMCREST][DEVICES]["Amcrest Camera"]
    assert device.serial_number == "SN-LIVE"
    mock_store.async_save.assert_called_once_with(
        {"serial_numbers": {"Amcrest Camera": "SN-LIVE"}}
    )


@pytest.mark.usefixtures("mock_event_monitor", "mock_discovery")
async def test_serial_loaded_from_storage_on_restart(
    hass: HomeAssistant,
    mock_store: MagicMock,
) -> None:
    """Stored serial number is used on restart without contacting the camera."""
    mock_store.async_load.return_value = {
        "serial_numbers": {"Amcrest Camera": "SN-STORED"}
    }

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        return_value=_CheckerOnline(),
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)

    device = hass.data[DATA_AMCREST][DEVICES]["Amcrest Camera"]
    # SN-STORED (from storage) confirms the camera serial was not fetched live
    assert device.serial_number == "SN-STORED"
    mock_store.async_save.assert_not_called()


@pytest.mark.parametrize(
    "checker",
    [
        pytest.param(_CheckerEmptySerial(), id="empty_serial"),
        pytest.param(_CheckerOffline(), id="camera_offline"),
    ],
)
@pytest.mark.usefixtures("mock_event_monitor", "mock_discovery")
async def test_uuid_fallback_when_serial_unavailable(
    hass: HomeAssistant,
    mock_store: MagicMock,
    checker: _CheckerEmptySerial | _CheckerOffline,
) -> None:
    """A stable UUID is generated and persisted when a serial number cannot be obtained."""
    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        return_value=checker,
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)

    device = hass.data[DATA_AMCREST][DEVICES]["Amcrest Camera"]
    assert device.serial_number is not None
    assert _UUID_RE.match(device.serial_number)
    saved_data = mock_store.async_save.call_args[0][0]
    assert saved_data["serial_numbers"]["Amcrest Camera"] == device.serial_number
