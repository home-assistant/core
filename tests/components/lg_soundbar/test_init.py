"""Test the lg_soundbar setup."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from zeroconf import DNSAddress, DNSText, RecordUpdate, RecordUpdateListener
from zeroconf.const import _CLASS_IN, _TYPE_A, _TYPE_TXT

from homeassistant.components.lg_soundbar.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

ENTITY_ID = "media_player.127_0_0_1"


async def test_setup_while_device_is_unreachable(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an unplugged soundbar does not prevent the setup."""
    mock_client.connected = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.start.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_unload(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading stops the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.stop.assert_awaited_once()


def address_record(address: str) -> RecordUpdate:
    """Return the update of an address record, as received at boot."""
    record = DNSAddress(
        "audiocast.local.", _TYPE_A, _CLASS_IN, 120, ip_address(address).packed
    )
    return RecordUpdate(record, None)


def find_listener(mock_async_zeroconf: MagicMock) -> RecordUpdateListener:
    """Return the mDNS listener the integration registered."""
    return mock_async_zeroconf.zeroconf.async_add_listener.call_args.args[0]


@pytest.mark.parametrize(
    ("connected", "record", "reconnects"),
    [
        pytest.param(False, address_record("127.0.0.1"), True, id="announced"),
        pytest.param(True, address_record("127.0.0.1"), False, id="connected"),
        pytest.param(False, address_record("127.0.0.2"), False, id="other_device"),
        pytest.param(
            False,
            RecordUpdate(
                DNSText("127.0.0.1.local.", _TYPE_TXT, _CLASS_IN, 120, b""), None
            ),
            False,
            id="not_an_address",
        ),
    ],
)
async def test_announcement_triggers_reconnect(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_async_zeroconf: MagicMock,
    connected: bool,
    record: RecordUpdate,
    reconnects: bool,
) -> None:
    """Test an mDNS record with the address of the soundbar skips the backoff."""
    await setup_integration(hass, mock_config_entry)
    mock_client.connected = connected

    find_listener(mock_async_zeroconf).async_update_records(
        mock_async_zeroconf.zeroconf, 0, [record]
    )

    assert mock_client.reconnect_now.called is reconnects


async def test_listener_removed_on_unload(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_async_zeroconf: MagicMock,
) -> None:
    """Test unloading stops listening to mDNS."""
    await setup_integration(hass, mock_config_entry)
    listener = find_listener(mock_async_zeroconf)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_async_zeroconf.zeroconf.async_remove_listener.assert_called_once_with(listener)


async def test_no_listener_for_hostname(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_async_zeroconf: MagicMock,
) -> None:
    """Test a soundbar configured by hostname relies on the backoff alone."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "soundbar.lan", CONF_PORT: DEFAULT_PORT},
        unique_id="uuid",
    )

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    mock_async_zeroconf.zeroconf.async_add_listener.assert_not_called()
