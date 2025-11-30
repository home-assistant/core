"""Common fixtures for the STIEBEL ELTRON tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.stiebel_eltron.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_stiebel_eltron_client() -> Generator[MagicMock]:
    """Mock a stiebel eltron client."""
    with (
        patch(
            "homeassistant.components.stiebel_eltron.StiebelEltronAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.stiebel_eltron.config_flow.StiebelEltronAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.update.return_value = True
        client.get_target_temp = MagicMock(return_value=22.5)
        client.get_current_temp = MagicMock(return_value=21.0)
        client.get_current_humidity = MagicMock(return_value=45.0)
        client.get_filter_alarm_status = MagicMock(return_value=False)
        client.get_operation = MagicMock(return_value="DAY MODE")
        client.set_operation = MagicMock()
        client.set_target_temp = MagicMock()
        yield client


@pytest.fixture(autouse=True)
def mock_modbus() -> Generator[MagicMock]:
    """Mock a modbus client."""
    with (
        patch(
            "homeassistant.components.stiebel_eltron.ModbusTcpClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.stiebel_eltron.config_flow.ModbusTcpClient",
            new=mock_client,
        ),
    ):
        yield mock_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 502},
    )
