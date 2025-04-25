"""Common fixtures for the STIEBEL ELTRON tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.stiebel_eltron import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.stiebel_eltron.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


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
def mock_async_init() -> Generator[MagicMock]:
    """Mock hass.config_entries.flow.async_init."""
    with patch(
        "homeassistant.config_entries.ConfigEntriesFlowManager.async_init",
        new_callable=AsyncMock,
    ) as mock_async_init:
        yield mock_async_init


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 502},
    )
