"""Lamarzocco session fixtures."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

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
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_lamarzocco: MagicMock
) -> MockConfigEntry:
    """Set up the LaMetric integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_lamarzocco() -> Generator[MagicMock, None, None]:
    """Return a mocked LM client."""
    with patch(
        "homeassistant.components.lamarzocco.coordinator.LaMarzoccoClient",
        autospec=True,
    ) as lamarzocco_mock, patch(
        "homeassistant.components.lamarzocco.config_flow.LaMarzoccoClient",
        new=lamarzocco_mock,
    ):
        lamarzocco = lamarzocco_mock.return_value

        lamarzocco.model_name = "GS3 AV"
        lamarzocco.true_model_name = "GS3 AV"
        lamarzocco.machine_name = MACHINE_NAME
        lamarzocco.serial_number = "GS01234"

        lamarzocco.firmware_version = "1.1"
        lamarzocco.latest_firmware_version = "1.1"
        lamarzocco.gateway_version = "v2.2-rc0"
        lamarzocco.latest_gateway_version = "v3.1-rc4"

        lamarzocco.connect.return_value = None
        lamarzocco.websocket_connect.return_value = None
        lamarzocco.update_local_machine_status.return_value = None

        lamarzocco.current_status = json.loads(
            load_fixture("current_status.json", DOMAIN)
        )

        lamarzocco.try_connect.return_value = {
            "machine_name": MACHINE_NAME,
            "serial_number": "GS01234",
        }
        yield lamarzocco
