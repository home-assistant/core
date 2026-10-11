"""Test shared FortiOS polling and tracker discovery."""

from datetime import timedelta
from unittest.mock import MagicMock, create_autospec, patch

from aiofortiosapi import FortiOSConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.fortios.client import FortiOSClient, FortiOSDevice
from homeassistant.components.fortios.const import DOMAIN
from homeassistant.const import CONF_HOST, STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MAC, SERIAL, USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_discovery_and_grace(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Create only online clients, share polls, and preserve grace after disappearance."""
    other_mac = "11:22:33:44:55:66"
    mock_client.update.return_value[other_mac] = FortiOSDevice(
        other_mac, "laptop", False
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    assert hass.states.get("device_tracker.laptop") is None
    mock_client.update.return_value = {
        MAC: FortiOSDevice(MAC, "phone", True),
        other_mac: FortiOSDevice(other_mac, "laptop", True),
    }
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("device_tracker")) == 2
    assert mock_client.update.call_count == 2
    mock_client.update.return_value = {}
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    freezer.tick(timedelta(seconds=181))
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("device_tracker.phone").state == STATE_NOT_HOME
    mock_client.update.return_value = {MAC: FortiOSDevice(MAC, "phone", True)}
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME
    assert len(hass.states.async_all("device_tracker")) == 2
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_empty_initial_scan(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Discovery remains active when the first scan is empty."""
    mock_client.update.return_value = {}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.async_all("device_tracker") == []
    mock_client.update.return_value = {MAC: FortiOSDevice(MAC, "phone", True)}
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.phone").state == STATE_HOME


async def test_poll_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed scan makes states unavailable and recovers on the next scan."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.update.side_effect = FortiOSConnectionError
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("device_tracker.phone").state == STATE_UNAVAILABLE
    mock_client.update.side_effect = None
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("device_tracker.phone").state == STATE_HOME


@pytest.mark.parametrize("failure_method", ["connect", "update"])
async def test_setup_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    failure_method: str,
) -> None:
    """A failure in either setup request schedules a retry."""
    getattr(mock_client, failure_method).side_effect = FortiOSConnectionError
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)


async def test_same_mac_on_two_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep trackers distinct when two FortiGate devices report the same MAC."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    other_serial = "FGT654321"
    other_client = create_autospec(FortiOSClient, instance=True)
    other_client.serial = other_serial
    other_client.connect.return_value = other_serial
    other_client.update.return_value = {MAC: FortiOSDevice(MAC, "phone", True)}
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT | {CONF_HOST: "192.168.1.2"},
        unique_id=other_serial,
    )
    other_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.fortios.FortiOSClient", return_value=other_client
    ):
        assert await hass.config_entries.async_setup(other_entry.entry_id)
        await hass.async_block_till_done()

    first = entity_registry.async_get("device_tracker.phone")
    second = entity_registry.async_get("device_tracker.phone_2")
    assert first.unique_id == f"{SERIAL}_{MAC}"
    assert first.config_entry_id == mock_config_entry.entry_id
    assert second.unique_id == f"{other_serial}_{MAC}"
    assert second.config_entry_id == other_entry.entry_id
    assert len(hass.states.async_all("device_tracker")) == 2

    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_client.update.call_count == 2
    assert other_client.update.call_count == 2
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert hass.states.get("device_tracker.phone").state == STATE_UNAVAILABLE
    assert hass.states.get("device_tracker.phone_2").state == STATE_HOME
