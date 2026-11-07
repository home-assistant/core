"""Common fixtures for the Duosida EV Charger tests."""

from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, MagicMock, patch

from duosida_ev import ChargerInfo, ChargerState, ChargerStatus, DiscoveredCharger
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.duosida_ev.const import DOMAIN
from homeassistant.const import CONF_HOST

from . import push_update

HOST = "192.168.1.100"
DEVICE_ID = "0300000000000000000"

CHARGER_INFO = ChargerInfo(
    device_id=DEVICE_ID,
    model="Mode3@32A",
    manufacturer="DUOSIDA",
    firmware="V2.5",
)

CHARGER_STATUS = ChargerStatus(
    state=ChargerState.CHARGING,
    raw_state=2,
    voltage=230.4,
    current=15.8,
    power=3640.3,
    total_energy=527.4,
    session_energy=5.5,
    temperature=31.0,
    cp_voltage=6.1,
    session_start=datetime(2026, 11, 7, 0, 22, tzinfo=UTC),
    transaction_id=42,
    id_tag="DirectWorkUser",
    received_at=datetime(2026, 11, 7, 2, 52, tzinfo=UTC),
)


def charger_status(**changes: object) -> ChargerStatus:
    """Return a new status snapshot, as the charger pushes one every ~10 s."""
    return replace(CHARGER_STATUS, **changes)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Duosida EV Charger",
        data={CONF_HOST: HOST},
        unique_id=DEVICE_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.duosida_ev.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_duosida_client() -> Generator[MagicMock]:
    """Return a mocked, connected charger session."""
    with patch(
        "homeassistant.components.duosida_ev.DuosidaClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.connected = True
        client.status = CHARGER_STATUS
        client.connect.return_value = CHARGER_INFO
        client.get_status.return_value = CHARGER_STATUS

        async def disconnect() -> None:
            # The library notifies its listeners when it closes a session.
            client.connected = False
            push_update(client)

        client.disconnect.side_effect = disconnect
        yield client


@pytest.fixture
def mock_broadcast_addresses() -> Generator[AsyncMock]:
    """Return mocked broadcast addresses of the enabled network adapters."""
    with patch(
        "homeassistant.components.duosida_ev.config_flow.async_get_ipv4_broadcast_addresses",
        return_value={IPv4Address("192.168.1.255")},
    ) as mock_addresses:
        yield mock_addresses


@pytest.fixture
def mock_discover_chargers(mock_broadcast_addresses: AsyncMock) -> Generator[AsyncMock]:
    """Return a mocked network discovery that finds one charger."""
    with patch(
        "homeassistant.components.duosida_ev.config_flow.discover_chargers",
        return_value=[DiscoveredCharger(host=HOST, mac="aa:bb:cc:dd:ee:ff")],
    ) as mock_discover:
        yield mock_discover


@pytest.fixture
def mock_identify_charger() -> Generator[AsyncMock]:
    """Return a mocked identification of the charger over a short session."""
    with patch(
        "homeassistant.components.duosida_ev.config_flow.identify_charger",
        return_value=CHARGER_INFO,
    ) as mock_identify:
        yield mock_identify
