"""Fixtures for the Touchline tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.touchline.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"


@pytest.fixture
def mock_pytouchline() -> Generator[MagicMock]:
    """Mock PyTouchline across all integration modules."""
    with (
        patch(
            "homeassistant.components.touchline.PyTouchline",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.touchline.config_flow.PyTouchline",
            new=mock_class,
        ),
        patch(
            "homeassistant.components.touchline.climate.PyTouchline",
            new=mock_class,
        ),
    ):
        instance = mock_class.return_value
        instance.get_number_of_devices.return_value = 1
        instance.get_controller_id.return_value = "controller-1"
        instance.get_name.return_value = "Zone 1"
        instance.get_device_id.return_value = 0
        instance.get_current_temperature.return_value = 21.5
        instance.get_target_temperature.return_value = 22.0
        instance.get_operation_mode.return_value = 0
        instance.get_week_program.return_value = 0
        yield instance


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.touchline.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_HOST,
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
        unique_id="controller-1",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pytouchline: MagicMock,
) -> MockConfigEntry:
    """Set up the Touchline integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
