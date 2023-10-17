"""Lamarzocco session fixtures."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import DEFAULT_CONF, MACHINE_NAME, USER_INPUT

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My LaMarzocco",
        domain=DOMAIN,
        data=DEFAULT_CONF | USER_INPUT,
        unique_id="very_unique",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.lamarzocco.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_lamarzocco: AsyncMock
) -> MockConfigEntry:
    """Set up the LaMetric integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_lamarzocco(request) -> Generator[AsyncMock, None, None]:
    """Return a mocked LM client."""
    with patch(
        "homeassistant.components.lamarzocco.coordinator.LaMarzoccoClient",
        autospec=True,
    ), patch(
        "homeassistant.components.lamarzocco.config_flow.LaMarzoccoClient",
        autospec=True,
    ) as lamarzocco_mock:
        lamarzocco = lamarzocco_mock.return_value
        lamarzocco.machine_info.return_value = {
            "machine_name": MACHINE_NAME,
            "serial_number": "GS01234",
        }
        lamarzocco.model_name.return_value = "GS3 AV"

        lamarzocco.firmware_version.return_value = "1.1"
        lamarzocco.latest_firmware_version.return_value = "1.1"
        lamarzocco.gateway_version.return_value = "v2.2-rc0"
        lamarzocco.latest_gateway_version.return_value = "v3.1-rc4"

        lamarzocco.connect.return_value = None
        lamarzocco.websocket_connect.return_value = None
        lamarzocco.update_local_machine_status.return_value = None

        lamarzocco.config.return_value = json.loads(load_fixture("config.json", DOMAIN))
        lamarzocco.statistics.return_value = json.loads(
            load_fixture("counters.json", DOMAIN)
        )

        lamarzocco._build_current_status()

        lamarzocco.try_connect.return_value = {
            "machine_name": MACHINE_NAME,
        }
        yield lamarzocco
