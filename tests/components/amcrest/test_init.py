"""Tests for the Amcrest integration setup."""

import re
from typing import Any
from unittest.mock import patch

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest.const import DATA_AMCREST, DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import CAMERA_CONFIG, STORAGE_KEY, stored_serials

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
    hass_storage: dict[str, Any],
) -> None:
    """Serial number is fetched from camera and persisted on first setup."""
    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        return_value=_CheckerOnline(),
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)

    device = hass.data[DATA_AMCREST][DEVICES]["Amcrest Camera"]
    assert device.serial_number == "SN-LIVE"
    assert hass_storage[STORAGE_KEY]["data"] == {
        "serial_numbers": {"Amcrest Camera": "SN-LIVE"}
    }


@pytest.mark.usefixtures("mock_event_monitor", "mock_discovery")
async def test_serial_loaded_from_storage_on_restart(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Stored serial number is used on restart without contacting the camera."""
    hass_storage[STORAGE_KEY] = stored_serials({"Amcrest Camera": "SN-STORED"})

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        return_value=_CheckerOnline(),
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)

    device = hass.data[DATA_AMCREST][DEVICES]["Amcrest Camera"]
    # SN-STORED (from storage) confirms the camera serial was not fetched live
    assert device.serial_number == "SN-STORED"
    assert hass_storage[STORAGE_KEY]["data"] == {
        "serial_numbers": {"Amcrest Camera": "SN-STORED"}
    }


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
    hass_storage: dict[str, Any],
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
    stored = hass_storage[STORAGE_KEY]["data"]["serial_numbers"]
    assert stored["Amcrest Camera"] == device.serial_number


@pytest.mark.usefixtures("mock_event_monitor", "mock_discovery")
async def test_stale_serials_pruned_from_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Serials for cameras no longer in the config are dropped from storage."""
    hass_storage[STORAGE_KEY] = stored_serials(
        {"Amcrest Camera": "SN-STORED", "Removed Camera": "SN-GONE"}
    )

    with patch(
        "homeassistant.components.amcrest.AmcrestChecker",
        return_value=_CheckerOnline(),
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)

    # The configured camera is kept; the one dropped from YAML is pruned.
    assert hass_storage[STORAGE_KEY]["data"] == {
        "serial_numbers": {"Amcrest Camera": "SN-STORED"}
    }
