"""Define fixtures available for all tests."""
from functools import wraps

from canary.api import Api
from pytest import fixture

from tests.async_mock import MagicMock, patch


def mock_canary_update(self, **kwargs):
    """Get the latest data from py-canary."""
    for location in self._api.get_locations():
        location_id = location.location_id

        self._locations_by_id[location_id] = location

        for device in location.devices:
            if device.is_online:
                self._readings_by_device_id[
                    device.device_id
                ] = self._api.get_latest_readings(device.device_id)


def mock_decorator(*args, **kwargs):
    """Mock decorator to patch unwanted decorators."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)

        return decorated_function

    return decorator


@fixture
def canary(hass):
    """Mock the CanaryApi for easier testing."""
    with patch.object(Api, "login", return_value=True), patch(
        "homeassistant.components.canary.CanaryData.update", mock_canary_update
    ), patch(
        "homeassistant.components.canary.Api"
    ) as mock_canary:
        instance = mock_canary.return_value = Api(
            "test-username",
            "test-password",
            1,
        )

        instance.login = MagicMock(return_value=True)
        instance.get_entries = MagicMock(return_value=[])
        instance.get_locations = MagicMock(return_value=[])
        instance.get_location = MagicMock(return_value=None)
        instance.get_modes = MagicMock(return_value=[])
        instance.get_readings = MagicMock(return_value=[])
        instance.get_latest_readings = MagicMock(return_value=[])
        instance.set_location_mode = MagicMock(return_value=None)

        yield mock_canary


# patch("homeassistant.util.Throttle", mock_decorator).start()
