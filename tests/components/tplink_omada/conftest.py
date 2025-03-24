"""Test fixtures for TP-Link Omada integration."""

from collections.abc import AsyncIterable, Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tplink_omada_client.clients import (
    OmadaConnectedClient,
    OmadaNetworkClient,
    OmadaWiredClient,
    OmadaWirelessClient,
)
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
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.tplink_omada.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_omada_site_client() -> Generator[AsyncMock]:
    """Mock Omada site client."""
    site_client = MagicMock()

    gateway_data = json.loads(load_fixture("gateway-TL-ER7212PC.json", DOMAIN))
    gateway = OmadaGateway(gateway_data)
    site_client.get_gateway = AsyncMock(return_value=gateway)

    switch1_data = json.loads(load_fixture("switch-TL-SG3210XHP-M2.json", DOMAIN))
    switch1 = OmadaSwitch(switch1_data)
    site_client.get_switches = AsyncMock(return_value=[switch1])

    devices_data = json.loads(load_fixture("devices.json", DOMAIN))
    devices = [OmadaListDevice(d) for d in devices_data]
    site_client.get_devices = AsyncMock(return_value=devices)

    switch1_ports_data = json.loads(
        load_fixture("switch-ports-TL-SG3210XHP-M2.json", DOMAIN)
    )
    switch1_ports = [OmadaSwitchPortDetails(p) for p in switch1_ports_data]
    site_client.get_switch_ports = AsyncMock(return_value=switch1_ports)

    async def async_empty() -> AsyncIterable:
        for c in ():
            yield c

    site_client.get_known_clients.return_value = async_empty()
    site_client.get_connected_clients.return_value = async_empty()
    return site_client


@pytest.fixture
def mock_omada_clients_only_site_client() -> Generator[AsyncMock]:
    """Mock Omada site client containing only client connection data."""
    site_client = MagicMock()

    site_client.get_switches = AsyncMock(return_value=[])
    site_client.get_devices = AsyncMock(return_value=[])
    site_client.get_switch_ports = AsyncMock(return_value=[])
    site_client.get_client = AsyncMock(side_effect=_get_mock_client)

    site_client.get_known_clients.side_effect = _get_mock_known_clients
    site_client.get_connected_clients.side_effect = _get_mock_connected_clients

    return site_client


async def _get_mock_known_clients() -> AsyncIterable[OmadaNetworkClient]:
    """Mock known clients of the Omada network."""
    known_clients_data = json.loads(load_fixture("known-clients.json", DOMAIN))
    for c in known_clients_data:
        if c["wireless"]:
            yield OmadaWirelessClient(c)
        else:
            yield OmadaWiredClient(c)


async def _get_mock_connected_clients() -> AsyncIterable[OmadaConnectedClient]:
    """Mock connected clients of the Omada network."""
    connected_clients_data = json.loads(load_fixture("connected-clients.json", DOMAIN))
    for c in connected_clients_data:
        if c["wireless"]:
            yield OmadaWirelessClient(c)
        else:
            yield OmadaWiredClient(c)


def _get_mock_client(mac: str) -> OmadaNetworkClient:
    """Mock an Omada client."""
    connected_clients_data = json.loads(load_fixture("connected-clients.json", DOMAIN))

    for c in connected_clients_data:
        if c["mac"] == mac:
            if c["wireless"]:
                return OmadaWirelessClient(c)
            return OmadaWiredClient(c)
    raise ValueError(f"Client with MAC {mac} not found in mock data")


@pytest.fixture
def mock_omada_client(mock_omada_site_client: AsyncMock) -> Generator[MagicMock]:
    """Mock Omada client."""
    with patch(
        "homeassistant.components.tplink_omada.create_omada_client",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value

        client.get_site_client.return_value = mock_omada_site_client
        yield client


@pytest.fixture
def mock_omada_clients_only_client(
    mock_omada_clients_only_site_client: AsyncMock,
) -> Generator[MagicMock]:
    """Mock Omada client."""
    with patch(
        "homeassistant.components.tplink_omada.create_omada_client",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value

        client.get_site_client.return_value = mock_omada_clients_only_site_client
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
