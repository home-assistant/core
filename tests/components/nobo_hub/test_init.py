"""Tests for the Nobø Ecohub integration setup."""

from unittest.mock import MagicMock, patch

from pynobo import nobo as pynobo_nobo
import pytest

from homeassistant.components.nobo_hub import async_setup_entry
from homeassistant.components.nobo_hub.const import (
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .conftest import SERIAL, STORED_IP

from tests.common import MockConfigEntry

NEW_IP = "192.168.1.55"


def _spec_hub(connect_exc: BaseException | None = None) -> MagicMock:
    """Build a minimal spec'd pynobo hub for rediscovery tests."""
    hub = MagicMock(spec=pynobo_nobo)
    if connect_exc is not None:
        hub.connect.side_effect = connect_exc
    hub.connected = True
    hub.hub_serial = SERIAL
    hub.hub_info = {
        "name": "My Eco Hub",
        "serial": SERIAL,
        "software_version": "115",
        "hardware_version": "hw",
    }
    hub.zones = {}
    hub.components = {}
    hub.week_profiles = {}
    hub.overrides = {}
    return hub


async def test_setup_uses_stored_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """Setup connects using the stored IP without invoking rediscovery."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_nobo_class.call_args.kwargs["ip"] == STORED_IP
    assert mock_nobo_class.call_args.kwargs["discover"] is False
    mock_nobo_class.async_discover_hubs.assert_not_called()


async def test_setup_rediscovery_updates_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed direct connect falls back to rediscovery and persists the new IP."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.nobo_hub.nobo", autospec=True) as mock_cls:
        mock_cls.side_effect = [
            _spec_hub(connect_exc=OSError("Unreachable")),
            _spec_hub(),
        ]
        mock_cls.async_discover_hubs.return_value = {(NEW_IP, SERIAL)}
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_IP_ADDRESS] == NEW_IP
    assert mock_cls.call_count == 2
    assert mock_cls.call_args_list[0].kwargs["ip"] == STORED_IP
    assert mock_cls.call_args_list[1].kwargs["ip"] == NEW_IP


@pytest.mark.parametrize(
    ("discovered_hubs", "second_exc", "expected_placeholders"),
    [
        (set(), None, {"serial": SERIAL, "ip": STORED_IP}),
        (
            {(NEW_IP, SERIAL)},
            OSError("Unreachable"),
            {"serial": SERIAL, "ip": NEW_IP},
        ),
    ],
    ids=["rediscovery_empty", "rediscovered_ip_fails"],
)
async def test_setup_rediscovery_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    discovered_hubs: set[tuple[str, str]],
    second_exc: BaseException | None,
    expected_placeholders: dict[str, str],
) -> None:
    """Setup raises cannot_connect when rediscovery can't recover."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.nobo_hub.nobo", autospec=True) as mock_cls:
        mock_cls.side_effect = [
            _spec_hub(connect_exc=OSError("Unreachable")),
            _spec_hub(connect_exc=second_exc),
        ]
        mock_cls.async_discover_hubs.return_value = discovered_hubs
        with pytest.raises(ConfigEntryNotReady) as exc_info:
            await async_setup_entry(hass, mock_config_entry)

    assert exc_info.value.translation_key == "cannot_connect"
    assert exc_info.value.translation_placeholders == expected_placeholders


@pytest.mark.parametrize(
    ("stored_options", "expected_options"),
    [
        ({CONF_OVERRIDE_TYPE: "Constant"}, {CONF_OVERRIDE_TYPE: "constant"}),
        ({CONF_OVERRIDE_TYPE: "Now"}, {CONF_OVERRIDE_TYPE: "now"}),
        ({CONF_OVERRIDE_TYPE: "constant"}, {CONF_OVERRIDE_TYPE: "constant"}),
        ({}, {}),
    ],
    ids=["Constant", "Now", "already_lowercase", "no_options"],
)
async def test_migrate_options(
    hass: HomeAssistant,
    mock_nobo_class: MagicMock,
    stored_options: dict[str, str],
    expected_options: dict[str, str],
) -> None:
    """Migrating from minor_version 1 lowercases override_type and bumps version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
        },
        options=stored_options,
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 3
    assert entry.options == expected_options


async def test_migrate_data_drops_auto_discovered(
    hass: HomeAssistant,
    mock_nobo_class: MagicMock,
) -> None:
    """The auto_discovered key is stripped from entry.data on migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
            "auto_discovered": True,
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 3
    assert entry.data == {CONF_SERIAL: SERIAL, CONF_IP_ADDRESS: STORED_IP}
    assert entry.options == {}


async def test_setup_registers_hub_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """The hub device is registered with the expected metadata."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device is not None
    assert device.config_entries == {mock_config_entry.entry_id}
    assert device.name == "My Eco Hub"
    assert device.manufacturer == "Glen Dimplex Nordic AS"
    assert device.model == "Nobø Ecohub"
    assert device.serial_number == SERIAL
    assert device.sw_version == "115"
    assert device.hw_version == "hw"
