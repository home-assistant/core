"""Tests for the AsusWrt device tracker."""

from datetime import timedelta
import logging

from aioasuswrt.asuswrt import Device as LegacyDevice
from asyncssh.constants import OPEN_ADMINISTRATIVELY_PROHIBITED, OPEN_CONNECT_FAILED
from asyncssh.misc import ChannelOpenError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components import device_tracker
from homeassistant.components.asuswrt.const import CONF_TRACK_UNKNOWN, DOMAIN
from homeassistant.const import CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    CONFIG_DATA_SSH,
    CONFIG_DATA_TELNET,
    MOCK_MACS,
    PROTOCOL_SSH,
    ROUTER_MAC_ADDR,
    new_device,
)


@pytest.mark.usefixtures("connect_legacy")
async def test_unnamed_client_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an unnamed client only names a new device by its MAC address."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_TELNET, unique_id=ROUTER_MAC_ADDR
    )
    config_entry.add_to_hass(hass)
    existing_mac = dr.format_mac(MOCK_MACS[2])
    new_mac = dr.format_mac(MOCK_MACS[3])
    # Offline clients restored from registry entries without a name
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        DOMAIN,
        existing_mac,
        config_entry=config_entry,
        original_name=existing_mac.replace(":", "_"),
    )
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN, DOMAIN, new_mac, config_entry=config_entry
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, existing_mac)},
        name="My phone",
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    existing_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, existing_mac), config_entry.entry_id
    )
    assert existing_device is not None
    assert existing_device.name == "My phone"
    new_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, new_mac), config_entry.entry_id
    )
    assert new_device is not None
    assert new_device.name == new_mac


@pytest.mark.usefixtures("connect_legacy")
async def test_connected_unnamed_client_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_devices_legacy: dict[str, LegacyDevice],
) -> None:
    """Test a connected unnamed client only names a new device by its MAC address."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA_TELNET,
        options={CONF_TRACK_UNKNOWN: True},
        unique_id=ROUTER_MAC_ADDR,
    )
    config_entry.add_to_hass(hass)
    existing_mac = dr.format_mac(MOCK_MACS[2])
    new_mac = dr.format_mac(MOCK_MACS[3])
    for mac, ip in ((MOCK_MACS[2], "192.168.1.4"), (MOCK_MACS[3], "192.168.1.5")):
        mock_devices_legacy[mac] = new_device(
            CONFIG_DATA_TELNET[CONF_PROTOCOL], mac, ip, None
        )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, existing_mac)},
        name="My phone",
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    existing_device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, existing_mac), config_entry.entry_id
    )
    assert existing_device is not None
    assert existing_device.name == "My phone"
    new_device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, new_mac), config_entry.entry_id
    )
    assert new_device_entry is not None
    assert new_device_entry.name == new_mac
    # The tracker of an unnamed client keeps its legacy name
    entity_id = entity_registry.async_get_entity_id(
        device_tracker.DOMAIN, DOMAIN, new_mac
    )
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.original_name == new_mac.replace(":", "_")


def _closed_session() -> ChannelOpenError:
    """Return the error aioasuswrt raises after the router drops SSH."""
    return ChannelOpenError(OPEN_CONNECT_FAILED, "SSH connection closed")


@pytest.mark.parametrize(
    ("closed_attempts", "expected_ip", "logs_error"),
    [
        pytest.param(1, "10.0.0.9", False, id="reconnect_once"),
        pytest.param(2, "192.168.1.2", True, id="second_attempt_keeps_state"),
    ],
)
async def test_closed_ssh_session_retries_query_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    connect_legacy,
    mock_devices_legacy: dict[str, LegacyDevice],
    caplog: pytest.LogCaptureFixture,
    closed_attempts: int,
    expected_ip: str,
    logs_error: bool,
) -> None:
    """Reopen a closed SSH session once and keep device state if that fails."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_SSH, unique_id=ROUTER_MAC_ADDR
    )
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        DOMAIN,
        MOCK_MACS[0],
        suggested_object_id="test",
        config_entry=config_entry,
        disabled_by=None,
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.test").attributes["ip"] == "192.168.1.2"

    updated = dict(mock_devices_legacy)
    updated[MOCK_MACS[0]] = new_device(PROTOCOL_SSH, MOCK_MACS[0], "10.0.0.9", "Test")
    failures = [_closed_session() for _ in range(closed_attempts)]
    connect_legacy.return_value.async_get_connected_devices.side_effect = [
        *failures,
        updated,
    ]

    with caplog.at_level(logging.ERROR):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.test").attributes["ip"] == expected_ip
    assert connect_legacy.return_value.async_disconnect.await_count == 1
    assert connect_legacy.return_value.connection.async_connect.await_count == 2
    assert connect_legacy.return_value.async_get_connected_devices.await_count == 3
    assert ("Error connecting to ASUS router" in caplog.text) is logs_error


async def test_other_ssh_channel_error_does_not_reconnect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    connect_legacy,
) -> None:
    """Leave the SSH session alone when the channel fails for another reason."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG_DATA_SSH, unique_id=ROUTER_MAC_ADDR
    )
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        device_tracker.DOMAIN,
        DOMAIN,
        MOCK_MACS[0],
        suggested_object_id="test",
        config_entry=config_entry,
        disabled_by=None,
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    connect_legacy.return_value.async_get_connected_devices.side_effect = (
        ChannelOpenError(OPEN_ADMINISTRATIVELY_PROHIBITED, "Session refused")
    )
    with pytest.raises(ChannelOpenError):
        await config_entry.runtime_data.update_devices()

    assert hass.states.get("device_tracker.test").attributes["ip"] == "192.168.1.2"
    assert connect_legacy.return_value.async_disconnect.await_count == 0
    assert connect_legacy.return_value.connection.async_connect.await_count == 1
