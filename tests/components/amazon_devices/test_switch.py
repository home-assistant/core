"""Tests for the Amazon Devices switch platform."""

from unittest.mock import AsyncMock, patch

from aioamazondevices.api import AmazonDevice
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.amazon_devices.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.amazon_devices.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_dnd(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switching DND."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "switch.echo_test_do_not_disturb"

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_do_not_disturb.call_count == 1

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_SERIAL_NUMBER: AmazonDevice(
            account_name="Echo Test",
            capabilities=["AUDIO_PLAYER", "MICROPHONE"],
            device_family="mine",
            device_type="echo",
            device_owner_customer_id="amazon_ower_id",
            device_cluster_members=[TEST_SERIAL_NUMBER],
            online=True,
            serial_number=TEST_SERIAL_NUMBER,
            software_version="echo_test_software_version",
            do_not_disturb=True,
            response_style=None,
            bluetooth_state=True,
        )
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_SERIAL_NUMBER: AmazonDevice(
            account_name="Echo Test",
            capabilities=["AUDIO_PLAYER", "MICROPHONE"],
            device_family="mine",
            device_type="echo",
            device_owner_customer_id="amazon_ower_id",
            device_cluster_members=[TEST_SERIAL_NUMBER],
            online=True,
            serial_number=TEST_SERIAL_NUMBER,
            software_version="echo_test_software_version",
            do_not_disturb=False,
            response_style=None,
            bluetooth_state=True,
        )
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_amazon_devices_client.set_do_not_disturb.call_count == 2
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
