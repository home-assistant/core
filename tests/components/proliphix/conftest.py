"""Test fixtures for Proliphix integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.proliphix.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.proliphix.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_proliphix():
    """Return a mocked Proliphix PDP instance."""
    with (
        patch(
            "homeassistant.components.proliphix.config_flow.PDP",
            autospec=True,
        ) as mock_class,
        patch("homeassistant.components.proliphix.PDP", new=mock_class),
    ):
        pdp = mock_class.return_value
        pdp.name = "Living Room Thermostat"
        pdp.cur_temp = 72.5
        pdp.setback = 70.0
        pdp.fan_state = "Auto"
        pdp.hvac_state = 3  # Heating
        pdp.is_heating = True
        pdp.is_cooling = False
        pdp.update.return_value = None

        yield pdp


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Proliphix Thermostat",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password123",
        },
        entry_id="01JZ8Z7KKH3FIXEDTESTENTRY01",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_proliphix: MagicMock,
) -> MockConfigEntry:
    """Set up the Proliphix integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
