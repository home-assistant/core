"""Tests for the Alexa Devices switch platform."""

from unittest.mock import AsyncMock, patch

from aioamazondevices.api import AmazonDevice, AmazonDeviceSensor
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_1_SN

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "switch.echo_test_do_not_disturb"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.SWITCH]):
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

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_do_not_disturb.call_count == 1

    mock_amazon_devices_client.get_devices_data.return_value[TEST_DEVICE_1_SN] = (
        AmazonDevice(
            account_name="Echo Test",
            capabilities=["AUDIO_PLAYER", "MICROPHONE"],
            device_family="mine",
            device_type="echo",
            device_owner_customer_id="amazon_ower_id",
            device_cluster_members=[TEST_DEVICE_1_SN],
            online=True,
            serial_number=TEST_DEVICE_1_SN,
            software_version="echo_test_software_version",
            entity_id="11111111-2222-3333-4444-555555555555",
            endpoint_id="G1234567890123456789012345678A",
            sensors={
                "dnd": AmazonDeviceSensor(
                    name="dnd", value=True, error=False, scale=None
                ),
                "temperature": AmazonDeviceSensor(
                    name="temperature", value="22.5", error=False, scale="CELSIUS"
                ),
            },
        )
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_amazon_devices_client.get_devices_data.return_value[TEST_DEVICE_1_SN] = (
        AmazonDevice(
            account_name="Echo Test",
            capabilities=["AUDIO_PLAYER", "MICROPHONE"],
            device_family="mine",
            device_type="echo",
            device_owner_customer_id="amazon_ower_id",
            device_cluster_members=[TEST_DEVICE_1_SN],
            online=True,
            serial_number=TEST_DEVICE_1_SN,
            software_version="echo_test_software_version",
            entity_id="11111111-2222-3333-4444-555555555555",
            endpoint_id="G1234567890123456789012345678A",
            sensors={
                "dnd": AmazonDeviceSensor(
                    name="dnd", value=False, error=False, scale=None
                ),
                "temperature": AmazonDeviceSensor(
                    name="temperature", value="22.5", error=False, scale="CELSIUS"
                ),
            },
        )
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_amazon_devices_client.set_do_not_disturb.call_count == 2
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_offline_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test offline device handling."""
    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = False

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].online = True

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE
