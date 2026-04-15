"""Tests for the TIS Control switch platform."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

ENTITY_ID = f"{SWITCH_DOMAIN}.tis_device_1_2_3_test_switch"

MOCK_RAW_API_RESPONSE = [
    {
        "name": "Test Switch",
        "device_id": [1, 2, 3],
        "channels": [{"Output": 1}],
        "is_protected": False,
        "gateway": "mock_gateway",
    }
]


@pytest.fixture
async def tis_switch(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> AsyncGenerator[MagicMock]:
    """Set up the TIS integration with a single mock switch and return the mock API instance."""
    mock_tis_api.get_entities.return_value = MOCK_RAW_API_RESPONSE

    with patch(
        "homeassistant.components.tis_control.switch.TISAPISwitch"
    ) as mock_api_switch_cls:
        # Configure the Switch Device wrapper mock.
        mock_switch_wrapper = mock_api_switch_cls.return_value
        mock_switch_wrapper.name = "Test Switch"
        mock_switch_wrapper.unique_id = "tis_1_2_3_ch1"
        mock_switch_wrapper.device_id = [1, 2, 3]
        mock_switch_wrapper.gateway = "mock_gateway"
        mock_switch_wrapper.channel_number = 1
        mock_switch_wrapper.is_on = None  # Initial state
        mock_switch_wrapper.available = True
        mock_switch_wrapper.request_update = AsyncMock()
        mock_switch_wrapper.turn_switch_on = AsyncMock()
        mock_switch_wrapper.turn_switch_off = AsyncMock()
        mock_switch_wrapper.register_callback = MagicMock()

        # Add and initialize the integration
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        yield mock_switch_wrapper


async def test_setup_and_properties(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tis_switch: MagicMock
) -> None:
    """Test switch setup, initial state, and properties."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == "TIS Device 1_2_3 Test Switch"

    tis_switch.register_callback.assert_called_once()
    tis_switch.request_update.assert_awaited_once()

    # Verify device-registry scoping
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_mock_gateway_1_2_3")}
    )
    assert device is not None
    assert device.name == "TIS Device 1_2_3"

    # Verify entity-registry scoping
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{mock_config_entry.entry_id}_tis_1_2_3_ch1"


async def test_setup_no_switches(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test setup when no switches are discovered."""
    mock_tis_api.get_entities.return_value = []

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_tis_api.get_entities.assert_awaited_with(platform=Platform.SWITCH)
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_turn_on_service(hass: HomeAssistant, tis_switch: MagicMock) -> None:
    """Test the turn_on service call."""
    # Successful turn_on
    tis_switch.turn_switch_on.return_value = True

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {"entity_id": ENTITY_ID}, blocking=True
    )

    tis_switch.turn_switch_on.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Failed turn_on
    tis_switch.turn_switch_on.reset_mock()
    tis_switch.turn_switch_on.return_value = False

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {"entity_id": ENTITY_ID}, blocking=True
    )

    tis_switch.turn_switch_on.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_turn_off_service(hass: HomeAssistant, tis_switch: MagicMock) -> None:
    """Test the turn_off service call."""
    # Successful turn_off
    tis_switch.turn_switch_off.return_value = True

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ENTITY_ID}, blocking=True
    )

    tis_switch.turn_switch_off.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # Failed turn_off
    tis_switch.turn_switch_off.reset_mock()
    tis_switch.turn_switch_off.return_value = False

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ENTITY_ID}, blocking=True
    )

    tis_switch.turn_switch_off.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_state_updates_from_callback(
    hass: HomeAssistant, tis_switch: MagicMock
) -> None:
    """Test entity state updates when the device pushes a new state."""
    callback = tis_switch.register_callback.call_args[0][0]

    # Device updates to ON
    tis_switch.is_on = True
    tis_switch.available = True
    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Device updates to OFF
    tis_switch.is_on = False
    tis_switch.available = True
    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # Device updates to Unavailable
    tis_switch.available = False
    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_setup_switch_no_name(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test switch setup when the device returns no name."""
    mock_raw_no_name = [
        {
            "name": None,
            "device_id": [1, 2, 3],
            "channels": [{"Output": 1}],
            "is_protected": False,
            "gateway": "mock_gateway",
        }
    ]
    mock_tis_api.get_entities.return_value = mock_raw_no_name

    with patch(
        "homeassistant.components.tis_control.switch.TISAPISwitch"
    ) as mock_api_switch_cls:
        mock_switch_wrapper = mock_api_switch_cls.return_value
        mock_switch_wrapper.name = None
        mock_switch_wrapper.unique_id = "tis_1_2_3_ch1"
        mock_switch_wrapper.device_id = [1, 2, 3]
        mock_switch_wrapper.gateway = "mock_gateway"
        mock_switch_wrapper.channel_number = 1
        mock_switch_wrapper.is_on = False
        mock_switch_wrapper.available = True
        mock_switch_wrapper.request_update = AsyncMock()
        mock_switch_wrapper.register_callback = MagicMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids(SWITCH_DOMAIN)

    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state is not None
    assert state.state == STATE_OFF
    assert state.name == "TIS Device 1_2_3 Channel 1"


async def test_invalid_appliance_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test switch setup ignores appliances with invalid channel or device_id data."""
    mock_tis_api.get_entities.return_value = [
        # Channels is not a list or is empty.
        {
            "name": "Invalid Channels Type",
            "device_id": [1, 2, 3],
            "channels": "not_a_list",
        },
        {
            "name": "No Channels",
            "device_id": [1, 2, 3],
            "channels": [],
        },
        # First channel is not a dict or is empty.
        {
            "name": "String Channel",
            "device_id": [1, 2, 3],
            "channels": ["not_a_dict"],
        },
        {
            "name": "Empty Dict Channel",
            "device_id": [1, 2, 3],
            "channels": [{}],
        },
        # First channel value is None.
        {
            "name": "None Value Channel",
            "device_id": [1, 2, 3],
            "channels": [{"Output": None}],
        },
        # ValueError (cannot cast string to int).
        {
            "name": "String Value Channel",
            "device_id": [1, 2, 3],
            "channels": [{"Output": "abc"}],
        },
        # TypeError (cannot cast list to int).
        {
            "name": "List Value Channel",
            "device_id": [1, 2, 3],
            "channels": [{"Output": [1]}],
        },
        # Invalid device_id tests
        {
            "name": "Device ID None",
            "device_id": None,
            "channels": [{"Output": 1}],
        },
        {
            "name": "Device ID not list",
            "device_id": "not_a_list",
            "channels": [{"Output": 1}],
        },
        {
            "name": "Device ID list of invalid strings",
            "device_id": ["not", "an", "int"],
            "channels": [{"Output": 1}],
        },
        # Valid channel and device_id to ensure the loop processes correctly.
        {
            "name": "Valid Switch",
            "device_id": [1, 2, 3],
            "channels": [{"Output": 1}],
            "is_protected": False,
            "gateway": "mock_gateway",
        },
    ]

    with patch(
        "homeassistant.components.tis_control.switch.TISAPISwitch"
    ) as mock_api_switch_cls:
        # Mock the wrapper so it doesn't fail on initialization.
        mock_switch_wrapper = mock_api_switch_cls.return_value
        mock_switch_wrapper.name = "Valid Switch"
        mock_switch_wrapper.unique_id = "tis_1_2_3_ch1"
        mock_switch_wrapper.device_id = [1, 2, 3]
        mock_switch_wrapper.gateway = "mock_gateway"
        mock_switch_wrapper.channel_number = 1
        mock_switch_wrapper.is_on = False
        mock_switch_wrapper.available = True
        mock_switch_wrapper.request_update = AsyncMock()
        mock_switch_wrapper.register_callback = MagicMock()

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify that only the single valid entity was created.
    entity_ids = hass.states.async_entity_ids(SWITCH_DOMAIN)
    assert len(entity_ids) == 1
    assert hass.states.get(entity_ids[0]).name == "TIS Device 1_2_3 Valid Switch"
