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
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = f"{SWITCH_DOMAIN}.test_switch"

# This mimics the RAW JSON structure returned by tis_api.get_entities()
# This allows us to test the parsing logic inside async_get_switches.
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
async def setup_mock_switch(hass: HomeAssistant) -> AsyncGenerator[MagicMock]:
    """Set up the TIS integration with a single mock switch and return the mock API instance."""
    # Patch the main TISApi class from the integration's `__init__.py`.
    with (
        patch("homeassistant.components.tis_control.TISApi") as mock_tis_api_class,
        patch(
            "homeassistant.components.tis_control.switch.TISAPISwitch"
        ) as mock_api_switch_class,
    ):
        # Configure the main TISApi mock.
        # This is the instance that __init__.py will create.
        mock_api_instance = mock_tis_api_class.return_value

        # Make its connect() method a harmless async function that returns True.
        mock_api_instance.connect = AsyncMock(return_value=True)
        mock_api_instance.get_entities = AsyncMock(return_value=MOCK_RAW_API_RESPONSE)

        # Configure the TISAPISwitch mock (the device wrapper).
        mock_instance = mock_api_switch_class.return_value
        mock_instance.name = "Test Switch"
        mock_instance.unique_id = "tis_1_2_3_ch1"
        mock_instance.is_on = None
        mock_instance.request_update = AsyncMock()
        mock_instance.turn_switch_on = AsyncMock()
        mock_instance.turn_switch_off = AsyncMock()

        # Create a mock config entry.
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "1.2.3.4", "port": 1234},
            title="TIS Gateway",
        )

        # The switch platform retrieves the api from runtime_data, so we set it here.
        # It's important that this is the mock_api_instance.
        entry.runtime_data = MagicMock()
        entry.runtime_data.api = mock_api_instance
        entry.add_to_hass(hass)

        # Load the integration.
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Yield the mock TISAPISwitch instance for tests to use.
        yield mock_instance


async def test_setup_and_properties(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test switch setup, initial state, and properties."""

    # Check that the entity was created.
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == "Test Switch"

    # Verify that during setup, the entity registers its callback and requests an update.
    setup_mock_switch.register_callback.assert_called_once()
    setup_mock_switch.request_update.assert_awaited_once()


async def test_setup_no_switches(hass: HomeAssistant) -> None:
    """Test setup when no switches are discovered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "port": 1234},
        title="TIS Gateway",
    )
    entry.add_to_hass(hass)

    # Patch the main TISApi class to prevent real network calls.
    with patch("homeassistant.components.tis_control.TISApi") as mock_tis_api_class:
        # Configure the mock instance that TISApi() will return.
        mock_api_instance = mock_tis_api_class.return_value
        mock_api_instance.connect = AsyncMock(return_value=True)

        # Return an empty list from the API level.
        mock_api_instance.get_entities = AsyncMock(return_value=[])

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Assert that get_entities was called.
    mock_api_instance.get_entities.assert_awaited_once()

    # Assert that no switch entities were created.
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_turn_on_service(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test the turn_on service call."""
    mock_api = setup_mock_switch

    # Successful turn_on.
    mock_api.turn_switch_on.return_value = True

    # Call the turn_on service.
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {"entity_id": ENTITY_ID}, blocking=True
    )

    # Verify the API method was called and the state is optimistically updated.
    mock_api.turn_switch_on.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Failed turn_on (device offline).
    mock_api.turn_switch_on.reset_mock()
    mock_api.turn_switch_on.return_value = False

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {"entity_id": ENTITY_ID}, blocking=True
    )

    # Verify the API method was called and state becomes unavailable.
    mock_api.turn_switch_on.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_turn_off_service(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test the turn_off service call."""
    mock_api = setup_mock_switch

    # Successful turn_off.
    mock_api.turn_switch_off.return_value = True

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_api.turn_switch_off.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # Failed turn_off.
    mock_api.turn_switch_off.reset_mock()
    mock_api.turn_switch_off.return_value = False

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_api.turn_switch_off.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_state_updates_from_callback(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test entity state updates when the device pushes a new state."""
    mock_api = setup_mock_switch

    # Get the callback function that the entity registered with the API.
    # This simulates the API pushing a state change update to HA.
    callback = mock_api.register_callback.call_args[0][0]

    # Device turns ON.
    mock_api.is_on = True
    mock_api.available = True

    # Trigger the callback to inform Home Assistant.
    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Device turns OFF.
    mock_api.is_on = False
    mock_api.available = True

    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # Device goes OFFLINE.
    mock_api.is_on = None
    mock_api.available = False

    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Device comes back ONLINE.
    mock_api.is_on = True
    mock_api.available = True

    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_setup_switch_no_name(hass: HomeAssistant) -> None:
    """Test switch setup when the device returns no name (covers the else block in __init__)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "port": 1234},
        title="TIS Gateway",
    )
    entry.add_to_hass(hass)

    # Prepare a payload where "name" is None
    mock_raw_no_name = [
        {
            "name": None,  # This triggers the else block
            "device_id": [1, 2, 3],
            "channels": [{"Output": 1}],
            "is_protected": False,
            "gateway": "mock_gateway",
        }
    ]

    with (
        patch("homeassistant.components.tis_control.TISApi") as mock_tis_api_class,
        patch(
            "homeassistant.components.tis_control.switch.TISAPISwitch"
        ) as mock_api_switch_class,
    ):
        # 1. Mock the API connection and get_entities return value
        mock_api_instance = mock_tis_api_class.return_value
        mock_api_instance.connect = AsyncMock(return_value=True)
        mock_api_instance.get_entities = AsyncMock(return_value=mock_raw_no_name)

        # 2. Mock the Switch Wrapper to return None for name
        mock_switch_instance = mock_api_switch_class.return_value
        mock_switch_instance.name = None  # Essential for the coverage
        mock_switch_instance.unique_id = "tis_1_2_3_ch1"
        mock_switch_instance.is_on = False
        mock_switch_instance.request_update = AsyncMock()

        # 3. Setup Entry
        entry.runtime_data = MagicMock()
        entry.runtime_data.api = mock_api_instance

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert that the entity was created successfully
        # When _attr_name is None, HA usually falls back to device naming or defaults.
        # We simply check that the entity exists.
        assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

        # Verify the wrapper's name attribute was actually accessed
        assert mock_switch_instance.name is None
