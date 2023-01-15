"""Collection of helpers."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import DOMAIN
from homeassistant.core import HomeAssistant

from .const import CONF_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_bridge_discover():
    """Mock the bridge discover method."""
    with patch("pycomfoconnect.bridge.Bridge.discover") as mock_bridge_discover:
        mock_bridge_discover.return_value[0].uuid.hex.return_value = "00"
        yield mock_bridge_discover


@pytest.fixture
def mock_comfoconnect_command():
    """Mock the ComfoConnect connect method."""
    with patch(
        "pycomfoconnect.comfoconnect.ComfoConnect._command"
    ) as mock_comfoconnect_command:
        yield mock_comfoconnect_command


# @pytest.fixture
# async def setup_sensor(hass, mock_bridge_discover, mock_comfoconnect_command):
#     """Set up demo sensor component."""
#     with assert_setup_component(1, DOMAIN):
#         await async_setup_component(hass, DOMAIN, VALID_CONFIG)
#         await hass.async_block_till_done()


@pytest.fixture()
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    return create_entry(hass)


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create fixture for adding config entry in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)
    return entry


def _patch_setup_entry():
    return patch(
        "homeassistant.components.comfoconnect.async_setup_entry", return_value=True
    )


def patch_config_flow(mocked_bridge: MagicMock):
    """Patch Comfoconnect config flow."""
    return patch(
        "homeassistant.components.comfoconnect.config_flow.Bridge",
        return_value=mocked_bridge,
    )


@pytest.fixture()
def mocked_bridge() -> MagicMock:
    """Create mocked comfoconnect device."""
    mocked_bridge = MagicMock()
    return mocked_bridge
