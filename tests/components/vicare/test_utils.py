"""Test ViCare utils."""

from datetime import timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareRoomSensor import RoomSensor
from PyViCare.PyViCareUtils import (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.vicare.utils import (
    filter_state,
    get_device_name,
    retry_after_from,
)

# From a real rate limit response: 2026-09-09T00:00:04.144Z.
QUOTA_RESET_MS = 1788912004144


@pytest.mark.parametrize(
    ("state", "expected_result"),
    [
        (None, None),
        ("unknown", None),
        ("nothing", None),
        ("levelOne", "levelOne"),
    ],
)
async def test_filter_state(
    state: str | None,
    expected_result: str | None,
) -> None:
    """Test filter_state."""

    assert filter_state(state) == expected_result


@pytest.mark.parametrize(
    ("now", "floor", "expected_result"),
    [
        ("2026-09-08 20:00:04+00:00", timedelta(seconds=60), 14400.144),
        # A reset already passed must not retry at once.
        ("2026-09-09 01:00:04+00:00", timedelta(seconds=60), 60),
        # The floor is the caller's interval, not a fixed minute.
        ("2026-09-09 01:00:04+00:00", timedelta(seconds=180), 180),
        # Nothing waits longer than the quota window.
        ("2026-09-06 00:00:04+00:00", timedelta(seconds=60), 86400),
    ],
)
async def test_retry_after_from(
    freezer: FrozenDateTimeFactory,
    now: str,
    floor: timedelta,
    expected_result: float,
) -> None:
    """Test the rate limit backoff is clamped to the caller's interval and a day."""
    freezer.move_to(now)
    error = PyViCareRateLimitError(
        {
            "extendedPayload": {
                "name": "development portal",
                "requestCountLimit": 1450,
                "limitReset": QUOTA_RESET_MS,
            }
        }
    )

    assert retry_after_from(error, floor) == expected_result


@pytest.mark.parametrize(
    ("reported_name", "expected_result"),
    [
        ("Office", "Office"),
        # The app keeps the padding of what the user typed.
        ("  Office  ", "Office"),
        # A device that exists in the app but was left unnamed.
        ("", None),
        ("   ", None),
    ],
)
async def test_get_device_name(
    reported_name: str,
    expected_result: str | None,
) -> None:
    """Test the name a device was given in the ViCare app."""
    device = Mock(spec=RoomSensor)
    device.getName.return_value = reported_name

    assert get_device_name(device) == expected_result


@pytest.mark.parametrize(
    "exception",
    [
        PyViCareNotSupportedFeatureError("device.name"),
        PyViCareRateLimitError(
            {
                "extendedPayload": {
                    "name": "development portal",
                    "requestCountLimit": 1450,
                    "limitReset": QUOTA_RESET_MS,
                }
            }
        ),
        PyViCareInvalidDataError("not json"),
        PyViCareDeviceCommunicationError({"extendedPayload": {"reason": "offline"}}),
        PyViCareInternalServerError(
            {"statusCode": 500, "message": "boom", "viErrorId": "abc"}
        ),
        requests.exceptions.ConnectionError(),
        ValueError(),
    ],
)
async def test_get_device_name_unreadable(exception: Exception) -> None:
    """Test a name that cannot be read falls back to no name."""
    device = Mock(spec=RoomSensor)
    device.getName.side_effect = exception

    assert get_device_name(device) is None


async def test_get_device_name_not_implemented() -> None:
    """Test a device class that does not offer the getter at all.

    Only some PyViCare classes implement `getName()`: zigbee devices, floor
    heating channels, heating circuits, leak sensors and room sensors. The
    `Device` base class the heat pumps and boilers derive from does not.
    """
    assert get_device_name(Mock(spec=PyViCareDevice)) is None
