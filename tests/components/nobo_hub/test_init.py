"""Tests for the Nobø Ecohub integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nobo_hub import async_setup_entry
from homeassistant.components.nobo_hub.const import (
    CONF_AUTO_DISCOVERED,
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

SERIAL = "102000013098"
STORED_IP = "192.168.1.122"
NEW_IP = "192.168.1.55"


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


@pytest.mark.parametrize(
    "connect_exc",
    [OSError("Unreachable"), TimeoutError("Handshake timed out")],
)
async def test_setup_manual_entry_connection_fails(
    hass: HomeAssistant,
    connect_exc: BaseException,
) -> None:
    """Manual entry raises ConfigEntryNotReady on socket errors or timeouts."""
    entry = _make_entry(hass, auto_discovered=False)
    hub = _make_hub_mock(connect_exc=connect_exc)
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
    hub_fail = _make_hub_mock(connect_exc=OSError("Unreachable"))
    hub_ok = _make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.side_effect = [hub_fail, hub_ok]
        mock_cls.async_discover_hubs = AsyncMock(return_value={(NEW_IP, SERIAL)})
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_IP_ADDRESS] == NEW_IP
    assert mock_cls.call_count == 2
    assert mock_cls.call_args_list[0].kwargs["ip"] == STORED_IP
    assert mock_cls.call_args_list[1].kwargs["ip"] == NEW_IP


@pytest.mark.parametrize(
    (
        "discovered_hubs",
        "rediscovered_connect_fails",
        "expected_key",
        "expected_placeholders",
    ),
    [
        (set(), False, "hub_not_found", {"serial": SERIAL}),
        ({(NEW_IP, SERIAL)}, True, "cannot_connect_rediscovered", {"ip": NEW_IP}),
    ],
    ids=["rediscovery_empty", "rediscovered_ip_fails"],
)
async def test_setup_autodiscovered_rediscovery_failure(
    hass: HomeAssistant,
    discovered_hubs: set[tuple[str, str]],
    rediscovered_connect_fails: bool,
    expected_key: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Auto-discovered entry raises the right error when rediscovery can't recover."""
    entry = _make_entry(hass, auto_discovered=True)
    hub_first = _make_hub_mock(connect_exc=OSError("Unreachable"))
    hub_second = _make_hub_mock(
        connect_exc=OSError("Unreachable") if rediscovered_connect_fails else None
    )
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.side_effect = [hub_first, hub_second]
        mock_cls.async_discover_hubs = AsyncMock(return_value=discovered_hubs)
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, entry)

    assert exc_info.value.translation_key == expected_key
    assert exc_info.value.translation_placeholders == expected_placeholders


@pytest.mark.parametrize(
    ("stored_value", "expected_value"),
    [
        ("Constant", "constant"),
        ("Now", "now"),
        ("constant", "constant"),
    ],
)
async def test_migrate_options_lowercases_override_type(
    hass: HomeAssistant,
    stored_value: str,
    expected_value: str,
) -> None:
    """Legacy capitalized override_type values are lowercased on migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
            CONF_AUTO_DISCOVERED: False,
        },
        options={CONF_OVERRIDE_TYPE: stored_value},
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    hub = _make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.options == {CONF_OVERRIDE_TYPE: expected_value}


async def test_migrate_options_without_override_type(hass: HomeAssistant) -> None:
    """Migration still bumps the version when no override_type is stored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
            CONF_AUTO_DISCOVERED: False,
        },
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    hub = _make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.options == {}


async def test_setup_registers_hub_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The hub device is registered with the expected metadata."""
    entry = _make_entry(hass, auto_discovered=False)
    hub = _make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device is not None
    assert device.config_entries == {entry.entry_id}
    assert device.name == "My Eco Hub"
    assert device.manufacturer == "Glen Dimplex Nordic AS"
    assert device.model == "Nobø Ecohub"
    assert device.serial_number == SERIAL
    assert device.sw_version == "115"
    assert device.hw_version == "hw"
