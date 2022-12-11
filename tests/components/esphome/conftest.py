"""esphome session fixtures."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from aioesphomeapi import APIClient
import pytest
from zeroconf import Zeroconf

from homeassistant.components.esphome import CONF_NOISE_PSK, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def esphome_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="ESPHome Device",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.2",
            CONF_PORT: 6053,
            CONF_PASSWORD: "pwd",
            CONF_NOISE_PSK: "12345678123456781234567812345678",
        },
        unique_id="11:22:33:44:55:aa",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the ESPHome integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_client():
    """Mock APIClient."""
    mock_client = Mock(spec=APIClient)

    def mock_constructor(
        address: str,
        port: int,
        password: str | None,
        *,
        client_info: str = "aioesphomeapi",
        keepalive: float = 15.0,
        zeroconf_instance: Zeroconf = None,
        noise_psk: str | None = None,
        expected_name: str | None = None,
    ):
        """Fake the client constructor."""
        mock_client.host = address
        mock_client.port = port
        mock_client.password = password
        mock_client.zeroconf_instance = zeroconf_instance
        mock_client.noise_psk = noise_psk
        return mock_client

    mock_client.side_effect = mock_constructor
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()

    with patch("homeassistant.components.esphome.APIClient", mock_client), patch(
        "homeassistant.components.esphome.config_flow.APIClient", mock_client
    ):
        yield mock_client
