"""Tests for the Alexa Devices switch platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from aioamazondevices.exceptions import CannotSetFeature
from aioamazondevices.structures import AmazonDevice
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import assert_device_removed_and_readded, setup_integration
from .const import (
    TEST_DEVICE_1,
    TEST_DEVICE_1_SN,
    TEST_DEVICE_2,
    TEST_DEVICE_2_SN,
    TEST_DEVICE_AQM,
    TEST_DEVICE_AQM_SN,
)

ENTITY_ID = "switch.echo_test_do_not_disturb"
LED_ENTITY_ID = "switch.air_quality_monitor_test_led_indicator"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "devices",
    [
        pytest.param({TEST_DEVICE_1_SN: TEST_DEVICE_1}, id="echo"),
        pytest.param({TEST_DEVICE_AQM_SN: TEST_DEVICE_AQM}, id="aqm"),
    ],
)
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    devices: dict[str, AmazonDevice],
) -> None:
    """Test all entities."""
    mock_amazon_devices_client.get_devices_data.return_value = deepcopy(devices)

    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_dnd(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switching DND updates state optimistically."""
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
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_do_not_disturb.call_count == 2
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_switch_dnd_pushed_event(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the DND switch reflects state pushed by the Amazon API."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    mock_amazon_devices_client.on_dnd_event.append.assert_called_once()
    event_handler = mock_amazon_devices_client.on_dnd_event.append.call_args.args[0]

    await event_handler({TEST_DEVICE_1_SN: True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    await event_handler({TEST_DEVICE_1_SN: False})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_switch_dnd_unavailable_when_missing_from_push(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the DND switch is unavailable while its state is missing from a push."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    event_handler = mock_amazon_devices_client.on_dnd_event.append.call_args.args[0]

    await event_handler({})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    await event_handler({TEST_DEVICE_1_SN: True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON


async def test_switch_dnd_not_created_without_synced_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the DND switch is not created until a DND state has been synced."""
    mock_amazon_devices_client.sync_dnd_state = AsyncMock()

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None


async def test_switch_dnd_created_by_late_pushed_event(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the DND switch is created by a push arriving after initial sync failed."""
    mock_amazon_devices_client.sync_dnd_state = AsyncMock()

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) is None

    mock_amazon_devices_client.on_dnd_event.append.assert_called_once()
    event_handler = mock_amazon_devices_client.on_dnd_event.append.call_args.args[0]
    await event_handler({TEST_DEVICE_1_SN: True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON


async def test_switch_dnd_created_for_new_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a DND switch is created for a device added while HA is running."""
    new_entity_id = "switch.echo_test_2_do_not_disturb"

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(new_entity_id) is None

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: TEST_DEVICE_1,
        TEST_DEVICE_2_SN: TEST_DEVICE_2,
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(new_entity_id))
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


async def test_device_removed_and_readded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities are recreated when a device is removed and re-added."""
    await assert_device_removed_and_readded(
        hass,
        freezer,
        mock_amazon_devices_client,
        mock_config_entry,
        entity_id=ENTITY_ID,
        devices_with={TEST_DEVICE_1_SN: TEST_DEVICE_1},
        devices_without={},
    )


async def test_switch_communication(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switching Communication."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "switch.echo_test_communications"

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_amazon_devices_client.set_communication_status.call_count == 1

    device_data = deepcopy(TEST_DEVICE_1)
    device_data.communication_settings = {
        "announcements": "ON",
        "communications": "OFF",
        "dropin": "All",
    }

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: device_data
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device_data.communication_settings = {
        "announcements": "ON",
        "communications": "ON",
        "dropin": "All",
    }

    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_1_SN: device_data
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_amazon_devices_client.set_communication_status.call_count == 2
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON


async def test_switch_led(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switching the AQM LED updates state optimistically."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_AQM_SN: deepcopy(TEST_DEVICE_AQM)
    }
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(LED_ENTITY_ID))
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: LED_ENTITY_ID},
        blocking=True,
    )

    mock_amazon_devices_client.call_feature_operation.assert_called_once_with(
        mock_amazon_devices_client.get_devices_data.return_value[TEST_DEVICE_AQM_SN],
        "toggle",
        "turnOff",
        command_payload=None,
        instance="11",
    )
    assert (state := hass.states.get(LED_ENTITY_ID))
    assert state.state == STATE_OFF

    mock_amazon_devices_client.call_feature_operation.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LED_ENTITY_ID},
        blocking=True,
    )

    mock_amazon_devices_client.call_feature_operation.assert_called_once_with(
        mock_amazon_devices_client.get_devices_data.return_value[TEST_DEVICE_AQM_SN],
        "toggle",
        "turnOn",
        command_payload=None,
        instance="11",
    )
    assert (state := hass.states.get(LED_ENTITY_ID))
    assert state.state == STATE_ON


async def test_switch_led_unavailable_on_sensor_error(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the AQM LED switch is unavailable when its sensor reports an error."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_AQM_SN: deepcopy(TEST_DEVICE_AQM)
    }
    mock_amazon_devices_client.sensors[TEST_DEVICE_AQM_SN]["aqm_led"].error = True
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(LED_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_switch_led_created_without_sensor_value(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the AQM LED switch is created from the feature before a value arrives."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_AQM_SN: deepcopy(TEST_DEVICE_AQM)
    }
    del mock_amazon_devices_client.sensors[TEST_DEVICE_AQM_SN]["aqm_led"]
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(LED_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


async def test_switch_led_not_created_without_feature(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the AQM LED switch is not created when the feature is unsupported."""
    device = deepcopy(TEST_DEVICE_AQM)
    device.features = {}
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_AQM_SN: device
    }
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(LED_ENTITY_ID) is None


async def test_switch_led_cannot_set_feature(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a rejected LED command raises and keeps the current state."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_AQM_SN: deepcopy(TEST_DEVICE_AQM)
    }
    mock_amazon_devices_client.call_feature_operation.side_effect = CannotSetFeature
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: LED_ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == "cannot_set_feature_with_error"
    assert (state := hass.states.get(LED_ENTITY_ID))
    assert state.state == STATE_ON
