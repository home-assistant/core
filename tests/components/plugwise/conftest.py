"""Setup mocks for the Plugwise integration tests."""
from __future__ import annotations

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.plugwise.const import API, DOMAIN, PW_TYPE
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def _read_json(environment: str, call: str) -> dict[str, Any]:
    """Undecode the json data."""
    fixture = load_fixture(f"plugwise/{environment}/{call}.json")
    return json.loads(fixture)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Plugwise",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_PASSWORD: "test-password",
            CONF_PORT: 80,
            CONF_USERNAME: "smile",
            PW_TYPE: API,
        },
        unique_id="smile98765",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.plugwise.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture()
def mock_smile_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked Smile client."""
    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
        autospec=True,
    ) as smile_mock:
        smile = smile_mock.return_value
        smile.smile_hostname = "smile12345"
        smile.smile_name = "Test Smile Name"
        smile.connect.return_value = True
        yield smile


@pytest.fixture
def mock_smile_adam() -> Generator[None, MagicMock, None]:
    """Create a Mock Adam environment for testing exceptions."""
    chosen_env = "adam_multiple_devices_per_zone"

    with patch(
        "homeassistant.components.plugwise.gateway.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "fe799307f1624099878210aa0b9f1475"
        smile.heater_id = "90986d591dcd426cae3ec3e8111ff730"
        smile.smile_version = "3.0.15"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_name = "Adam"

        smile.connect.return_value = True

        smile.notifications = _read_json(chosen_env, "notifications")
        smile.async_update.return_value = _read_json(chosen_env, "all_data")

        yield smile


@pytest.fixture
def mock_smile_anna() -> Generator[None, MagicMock, None]:
    """Create a Mock Anna environment for testing exceptions."""
    chosen_env = "anna_heatpump"
    with patch(
        "homeassistant.components.plugwise.gateway.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "015ae9ea3f964e668e490fa39da3870b"
        smile.heater_id = "1cbf783bb11e4a7c8a6843dee3a86927"
        smile.smile_version = "4.0.15"
        smile.smile_type = "thermostat"
        smile.smile_hostname = "smile98765"
        smile.smile_name = "Anna"

        smile.connect.return_value = True

        smile.notifications = _read_json(chosen_env, "notifications")
        smile.async_update.return_value = _read_json(chosen_env, "all_data")

        yield smile


@pytest.fixture
def mock_smile_p1() -> Generator[None, MagicMock, None]:
    """Create a Mock P1 DSMR environment for testing exceptions."""
    chosen_env = "p1v3_full_option"
    with patch(
        "homeassistant.components.plugwise.gateway.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "e950c7d5e1ee407a858e2a8b5016c8b3"
        smile.heater_id = None
        smile.smile_version = "3.3.9"
        smile.smile_type = "power"
        smile.smile_hostname = "smile98765"
        smile.smile_name = "Smile P1"

        smile.connect.return_value = True

        smile.notifications = _read_json(chosen_env, "notifications")
        smile.async_update.return_value = _read_json(chosen_env, "all_data")

        yield smile


@pytest.fixture
def mock_stretch() -> Generator[None, MagicMock, None]:
    """Create a Mock Stretch environment for testing exceptions."""
    chosen_env = "stretch_v31"
    with patch(
        "homeassistant.components.plugwise.gateway.Smile", autospec=True
    ) as smile_mock:
        smile = smile_mock.return_value

        smile.gateway_id = "259882df3c05415b99c2d962534ce820"
        smile.heater_id = None
        smile.smile_version = "3.1.11"
        smile.smile_type = "stretch"
        smile.smile_hostname = "stretch98765"
        smile.smile_name = "Stretch"

        smile.connect.return_value = True
        smile.async_update.return_value = _read_json(chosen_env, "all_data")

        yield smile


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Plugwise integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
