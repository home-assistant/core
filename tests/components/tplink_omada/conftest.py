"""Test fixtures for TP-Link Omada integration."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tplink_omada_client.devices import (
    OmadaGateway,
    OmadaListDevice,
    OmadaSwitch,
    OmadaSwitchPortDetails,
)

from homeassistant.components.tplink_omada.config_flow import CONF_SITE
from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "mocked-password",
            CONF_USERNAME: "mocked-user",
            CONF_VERIFY_SSL: False,
            CONF_SITE: "Default",
        },
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.tplink_omada.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_omada_site_client() -> Generator[AsyncMock, None, None]:
    """Mock Omada site client."""
    site_client = AsyncMock()

    gateway_data = json.loads(load_fixture("gateway-TL-ER7212PC.json", DOMAIN))
    gateway = OmadaGateway(gateway_data)
    site_client.get_gateway.return_value = gateway

    switch1_data = json.loads(load_fixture("switch-TL-SG3210XHP-M2.json", DOMAIN))
    switch1 = OmadaSwitch(switch1_data)
    site_client.get_switches.return_value = [switch1]

    devices_data = json.loads(load_fixture("devices.json", DOMAIN))
    devices = [OmadaListDevice(d) for d in devices_data]
    site_client.get_devices.return_value = devices

    switch1_ports_data = json.loads(
        load_fixture("switch-ports-TL-SG3210XHP-M2.json", DOMAIN)
    )
    switch1_ports = [OmadaSwitchPortDetails(p) for p in switch1_ports_data]
    site_client.get_switch_ports.return_value = switch1_ports

    return site_client


@pytest.fixture
def mock_omada_client(
    mock_omada_site_client: AsyncMock,
) -> Generator[MagicMock, None, None]:
    """Mock Omada client."""
    with patch(
        "homeassistant.components.tplink_omada.create_omada_client",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value

        client.get_site_client.return_value = mock_omada_site_client
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_client: MagicMock,
) -> MockConfigEntry:
    """Set up the TP-Link Omada integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
