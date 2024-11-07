"""Common fixtures for the acaia tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyacaia_async.acaiascale import AcaiaDeviceState
from pyacaia_async.const import UnitMass as AcaiaUnitOfMass
import pytest

from homeassistant.components.acaia.const import CONF_IS_NEW_STYLE_SCALE, DOMAIN
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.acaia.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My scale",
        domain=DOMAIN,
        version=1,
        data={
            CONF_NAME: "LUNAR_123456",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
            CONF_IS_NEW_STYLE_SCALE: True,
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_scale: MagicMock
) -> None:
    """Set up the acaia integration for testing."""
    await setup_integration(hass, mock_config_entry, mock_scale)


@pytest.fixture
def mock_scale() -> Generator[MagicMock]:
    """Return a mocked acaia scale client."""
    with (
        patch(
            "homeassistant.components.acaia.coordinator.AcaiaScale",
            autospec=True,
        ) as scale_mock,
    ):
        scale = scale_mock.return_value
        scale.connected = True
        scale.mac = "aa:bb:cc:dd:ee:ff"
        scale.timer_running = True
        scale.heartbeat_task = None
        scale.process_queue_task = None
        scale.device_state = AcaiaDeviceState(
            battery_level=42, units=AcaiaUnitOfMass.GRAMS
        )
        scale.weight = 123.45
        yield scale
