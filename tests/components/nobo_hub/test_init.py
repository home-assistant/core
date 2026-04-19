"""Tests for the Nobø Ecohub integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nobo_hub import async_setup_entry
from homeassistant.components.nobo_hub.const import (
    CONF_AUTO_DISCOVERED,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry

SERIAL = "102000013098"
STORED_IP = "192.168.1.122"


def _make_entry(
    hass: HomeAssistant,
    *,
    auto_discovered: bool,
    ip_address: str = STORED_IP,
) -> MockConfigEntry:
    """Create a mock config entry for Nobø Ecohub."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: ip_address,
            CONF_AUTO_DISCOVERED: auto_discovered,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _make_hub_mock(connect_exc: BaseException | None = None) -> MagicMock:
    """Create a mock pynobo.nobo instance."""
    hub = MagicMock()
    hub.connect = AsyncMock(side_effect=connect_exc)
    hub.start = AsyncMock()
    hub.stop = AsyncMock()
    hub.register_callback = MagicMock()
    hub.deregister_callback = MagicMock()
    hub.hub_serial = SERIAL
    hub.hub_info = {
        "name": "My Eco Hub",
        "serial": SERIAL,
        "software_version": "115",
        "hardware_version": "hw",
    }
    hub.zones = {}
    hub.components = {}
    hub.overrides = {}
    hub.week_profiles = {}
    return hub


async def test_setup_manual_entry_uses_stored_ip(hass: HomeAssistant) -> None:
    """Manual entry connects using the stored IP without rediscovery."""
    entry = _make_entry(hass, auto_discovered=False)
    hub = _make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert mock_cls.call_args.kwargs["ip"] == STORED_IP
    assert mock_cls.call_args.kwargs["discover"] is False
    mock_cls.async_discover_hubs.assert_not_called()


async def test_setup_autodiscovered_entry_uses_stored_ip(hass: HomeAssistant) -> None:
    """Auto-discovered entry with a working stored IP does not rediscover."""
    entry = _make_entry(hass, auto_discovered=True)
    hub = _make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_cls.async_discover_hubs.assert_not_called()


async def test_setup_manual_entry_connection_fails(hass: HomeAssistant) -> None:
    """Manual entry raises ConfigEntryNotReady when the stored IP is unreachable."""
    entry = _make_entry(hass, auto_discovered=False)
    hub = _make_hub_mock(connect_exc=OSError("Unreachable"))
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, entry)

    assert exc_info.value.translation_key == "cannot_connect_manual"
    assert exc_info.value.translation_placeholders == {
        "serial": SERIAL,
        "ip": STORED_IP,
    }
    mock_cls.async_discover_hubs.assert_not_called()


async def test_setup_autodiscovered_rediscovery_updates_ip(hass: HomeAssistant) -> None:
    """Auto-discovered entry recovers via rediscovery and persists the new IP."""
    entry = _make_entry(hass, auto_discovered=True)
    new_ip = "192.168.1.55"
    hub_fail = _make_hub_mock(connect_exc=OSError("Unreachable"))
    hub_ok = _make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.side_effect = [hub_fail, hub_ok]
        mock_cls.async_discover_hubs = AsyncMock(return_value={(new_ip, SERIAL)})
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_IP_ADDRESS] == new_ip
    assert mock_cls.call_count == 2
    assert mock_cls.call_args_list[0].kwargs["ip"] == STORED_IP
    assert mock_cls.call_args_list[1].kwargs["ip"] == new_ip


async def test_setup_autodiscovered_rediscovery_empty(hass: HomeAssistant) -> None:
    """Auto-discovered entry raises hub_not_found when rediscovery finds nothing."""
    entry = _make_entry(hass, auto_discovered=True)
    hub_fail = _make_hub_mock(connect_exc=OSError("Unreachable"))
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub_fail
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, entry)

    assert exc_info.value.translation_key == "hub_not_found"
    assert exc_info.value.translation_placeholders == {"serial": SERIAL}


async def test_setup_autodiscovered_rediscovered_ip_fails(hass: HomeAssistant) -> None:
    """Auto-discovered entry raises cannot_connect_rediscovered when the new IP also fails."""
    entry = _make_entry(hass, auto_discovered=True)
    new_ip = "192.168.1.55"
    hub_fail_first = _make_hub_mock(connect_exc=OSError("Unreachable"))
    hub_fail_second = _make_hub_mock(connect_exc=OSError("Unreachable"))
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.side_effect = [hub_fail_first, hub_fail_second]
        mock_cls.async_discover_hubs = AsyncMock(return_value={(new_ip, SERIAL)})
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, entry)

    assert exc_info.value.translation_key == "cannot_connect_rediscovered"
    assert exc_info.value.translation_placeholders == {"ip": new_ip}
