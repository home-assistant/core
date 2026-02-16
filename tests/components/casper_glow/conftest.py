"""Casper Glow session fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pycasperglow import GlowState
import pytest

from homeassistant.components.casper_glow.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import CASPER_GLOW_DISCOVERY_INFO, setup_integration

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Casper Glow config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Jar",
        data={CONF_ADDRESS: CASPER_GLOW_DISCOVERY_INFO.address},
        unique_id=format_mac(CASPER_GLOW_DISCOVERY_INFO.address),
    )


@pytest.fixture
def mock_casper_glow() -> Generator[MagicMock]:
    """Mock a CasperGlow device."""
    with (
        patch(
            "homeassistant.components.casper_glow.CasperGlow",
            autospec=True,
        ) as mock_device_class,
        patch(
            "homeassistant.components.casper_glow.config_flow.CasperGlow",
            new=mock_device_class,
        ),
    ):
        mock_device = mock_device_class.return_value
        mock_device.address = CASPER_GLOW_DISCOVERY_INFO.address
        mock_device.state = GlowState()
        yield mock_device


@pytest.fixture
async def config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> MockConfigEntry:
    """Set up a Casper Glow config entry."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
