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

from tests.common import MockConfigEntry

ENTITY_ID = f"{SWITCH_DOMAIN}.test_switch"

# This mimics the RAW JSON structure returned by tis_api.get_entities().
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

    # 1. Patch the class AS IT IS IMPORTED IN YOUR __init__.py.
    with (
        patch("homeassistant.components.tis_control.TISApi") as mock_tis_api_cls,
        patch(
            "homeassistant.components.tis_control.switch.TISAPISwitch"
        ) as mock_api_switch_cls,
    ):
        # Configure the main API client mock.
        mock_api_instance = mock_tis_api_cls.return_value

        # Both connect and scan_devices are awaited in __init__.py.
        mock_api_instance.connect = AsyncMock()
        mock_api_instance.scan_devices = AsyncMock()

        mock_api_instance.get_entities = AsyncMock(return_value=MOCK_RAW_API_RESPONSE)

        # Configure the Switch Device wrapper mock.
        mock_switch_wrapper = mock_api_switch_cls.return_value
        mock_switch_wrapper.name = "Test Switch"
        mock_switch_wrapper.unique_id = "tis_1_2_3_ch1"
        mock_switch_wrapper.is_on = None  # Initial state.
        mock_switch_wrapper.available = True
        mock_switch_wrapper.request_update = AsyncMock()
        mock_switch_wrapper.turn_switch_on = AsyncMock()
        mock_switch_wrapper.turn_switch_off = AsyncMock()
        mock_switch_wrapper.register_callback = MagicMock()

        # Create the Config Entry.
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "1.2.3.4", "port": 1234},
            title="TIS Gateway",
        )
        entry.add_to_hass(hass)

        # Initialize the integration.
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Yield the wrapper so tests can assert against it.
        yield mock_switch_wrapper


async def test_setup_and_properties(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test switch setup, initial state, and properties."""
    # Check that the entity was created and state is sane.
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == "Test Switch"

    # Verify that during setup, the entity registers its callback and requests an update..
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

    # Patch the class in __init__.py specifically.
    with patch("homeassistant.components.tis_control.TISApi") as mock_tis_api_cls:
        mock_api_instance = mock_tis_api_cls.return_value

        # Ensure methods awaited in __init__ are AsyncMock.
        mock_api_instance.connect = AsyncMock()
        mock_api_instance.scan_devices = AsyncMock()

        # Return empty list.
        mock_api_instance.get_entities = AsyncMock(return_value=[])

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Assert get_entities was called.
        mock_api_instance.get_entities.assert_awaited_with(platform=Platform.SWITCH)

        # Assert no entities created.
        assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_turn_on_service(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test the turn_on service call."""
    mock_wrapper = setup_mock_switch

    # 1. Successful turn_on.
    mock_wrapper.turn_switch_on.return_value = True

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_wrapper.turn_switch_on.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    # 2. Failed turn_on (device offline/no ack).
    mock_wrapper.turn_switch_on.reset_mock()
    mock_wrapper.turn_switch_on.return_value = False

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_wrapper.turn_switch_on.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_turn_off_service(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test the turn_off service call."""
    mock_wrapper = setup_mock_switch

    # 1. Successful turn_off.
    mock_wrapper.turn_switch_off.return_value = True

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_wrapper.turn_switch_off.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF

    # 2. Failed turn_off.
    mock_wrapper.turn_switch_off.reset_mock()
    mock_wrapper.turn_switch_off.return_value = False

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ENTITY_ID}, blocking=True
    )

    mock_wrapper.turn_switch_off.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_state_updates_from_callback(
    hass: HomeAssistant, setup_mock_switch: MagicMock
) -> None:
    """Test entity state updates when the device pushes a new state."""
    mock_wrapper = setup_mock_switch

    # Retrieve the callback function stored in the mock.
    # This will now work because setup_mock_switch completed successfully.
    callback = mock_wrapper.register_callback.call_args[0][0]

    # 1. Device updates to ON.
    mock_wrapper.is_on = True
    mock_wrapper.available = True
    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # 2. Device updates to OFF.
    mock_wrapper.is_on = False
    mock_wrapper.available = True
    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # 3. Device updates to Unavailable.
    mock_wrapper.available = False
    callback()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_setup_switch_no_name(hass: HomeAssistant) -> None:
    """Test switch setup when the device returns no name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "port": 1234},
        title="TIS Gateway",
    )
    entry.add_to_hass(hass)

    # API response with None as name.
    mock_raw_no_name = [
        {
            "name": None,
            "device_id": [1, 2, 3],
            "channels": [{"Output": 1}],
            "is_protected": False,
            "gateway": "mock_gateway",
        }
    ]

    with (
        patch("homeassistant.components.tis_control.TISApi") as mock_tis_api_cls,
        patch(
            "homeassistant.components.tis_control.switch.TISAPISwitch"
        ) as mock_api_switch_cls,
    ):
        mock_api_instance = mock_tis_api_cls.return_value

        # Ensure methods awaited in __init__ are AsyncMock.
        mock_api_instance.connect = AsyncMock()
        mock_api_instance.scan_devices = AsyncMock()

        mock_api_instance.get_entities = AsyncMock(return_value=mock_raw_no_name)

        mock_switch_wrapper = mock_api_switch_cls.return_value
        mock_switch_wrapper.name = None
        mock_switch_wrapper.unique_id = "tis_1_2_3_ch1"
        mock_switch_wrapper.is_on = False
        mock_switch_wrapper.available = True
        mock_switch_wrapper.request_update = AsyncMock()
        mock_switch_wrapper.register_callback = MagicMock()

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Dynamically get the entity ID because it won't be 'switch.test_switch'.
        # when the name is None..
        entity_ids = hass.states.async_entity_ids(SWITCH_DOMAIN)

        # Assert that exactly one switch was created.
        assert len(entity_ids) == 1

        # Get the state of that entity.
        state = hass.states.get(entity_ids[0])
        assert state is not None

        # Verify the state is correct (e.g. OFF as defined in mock).
        assert state.state == STATE_OFF
