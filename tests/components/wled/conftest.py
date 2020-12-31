"""wled conftest."""
import pytest

from tests.common import mock_device_registry
from tests.components.light.conftest import mock_light_profiles  # noqa


@pytest.fixture
def device_registry(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)
