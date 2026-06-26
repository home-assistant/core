"""Tests for the Nobø Ecohub integration setup."""

from unittest.mock import MagicMock

from pynobo import nobo as pynobo_nobo
import pytest

from homeassistant.components.nobo_hub.const import (
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import SERIAL, STORED_IP

from tests.common import MockConfigEntry

NEW_IP = "192.168.1.55"


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
    mock_nobo_class: MagicMock,
) -> None:
    """A failed direct connect falls back to rediscovery and persists the new IP."""
    mock_config_entry.add_to_hass(hass)
    failing_hub = MagicMock(spec=pynobo_nobo)
    failing_hub.connect.side_effect = OSError("Unreachable")
    mock_nobo_class.side_effect = [failing_hub, mock_nobo_class.return_value]
    mock_nobo_class.async_discover_hubs.return_value = {(NEW_IP, SERIAL)}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_IP_ADDRESS] == NEW_IP
    assert mock_nobo_class.call_count == 2
    assert mock_nobo_class.call_args_list[0].kwargs["ip"] == STORED_IP
    assert mock_nobo_class.call_args_list[1].kwargs["ip"] == NEW_IP


async def test_setup_retries_when_rediscovery_finds_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """Setup retries when stored IP fails and rediscovery is empty."""
    mock_config_entry.add_to_hass(hass)
    failing_hub = MagicMock(spec=pynobo_nobo)
    failing_hub.connect.side_effect = OSError("Unreachable")
    mock_nobo_class.side_effect = [failing_hub]
    mock_nobo_class.async_discover_hubs.return_value = set()

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "serial": SERIAL,
        "ip": STORED_IP,
    }


async def test_setup_retries_when_rediscovered_ip_also_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """Setup retries when both stored and rediscovered IPs fail."""
    mock_config_entry.add_to_hass(hass)
    first_failing_hub = MagicMock(spec=pynobo_nobo)
    first_failing_hub.connect.side_effect = OSError("Unreachable")
    second_failing_hub = MagicMock(spec=pynobo_nobo)
    second_failing_hub.connect.side_effect = OSError("Unreachable")
    mock_nobo_class.side_effect = [first_failing_hub, second_failing_hub]
    mock_nobo_class.async_discover_hubs.return_value = {(NEW_IP, SERIAL)}

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "serial": SERIAL,
        "ip": NEW_IP,
    }


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
    assert entry.data == {
        CONF_SERIAL: SERIAL,
        CONF_IP_ADDRESS: STORED_IP,
    }
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
    assert device.connections == set()


async def test_setup_registers_hub_device_with_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_nobo_class: MagicMock,
) -> None:
    """An entry with a stored MAC surfaces it via DeviceInfo.connections."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
            CONF_MAC: "7C8306011192",
        },
        version=1,
        minor_version=3,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device is not None
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, "7c:83:06:01:11:92"),
    }
