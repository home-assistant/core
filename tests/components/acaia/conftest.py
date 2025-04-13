"""Common fixtures for the acaia tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioacaia.acaiascale import AcaiaDeviceState
from aioacaia.const import UnitMass as AcaiaUnitOfMass
import pytest

from homeassistant.components.acaia.const import CONF_IS_NEW_STYLE_SCALE, DOMAIN
from homeassistant.const import CONF_ADDRESS
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
def mock_verify() -> Generator[AsyncMock]:
    """Override is_new_scale check."""
    with patch(
        "homeassistant.components.acaia.config_flow.is_new_scale", return_value=True
    ) as mock_verify:
        yield mock_verify


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="LUNAR-DDEEFF",
        domain=DOMAIN,
        version=1,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_IS_NEW_STYLE_SCALE: True,
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_scale: MagicMock
) -> MockConfigEntry:
    """Set up the acaia integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


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
        scale.model = "Lunar"
        scale.last_disconnect_time = "1732181388.1895587"
        scale.timer_running = True
        scale.heartbeat_task = None
        scale.process_queue_task = None
        scale.device_state = AcaiaDeviceState(
            battery_level=42, units=AcaiaUnitOfMass.OUNCES
        )
        scale.weight = 123.45
        scale.timer = 23
        scale.flow_rate = 1.23
        yield scale
