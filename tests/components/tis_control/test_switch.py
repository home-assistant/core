"""."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tis_control.const import DEVICES_DICT
from homeassistant.components.tis_control.switch import async_setup_entry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import MockTISApi

SWITCH_DETAILS = {
    "name": "rcu_1",
    "device_id": [1, 48],
    "channel_number": 1,
    "unique_id": "switch.rcu_1",
}


@pytest.mark.asyncio
async def test_async_setup_entry_with_switches(
    hass: HomeAssistant, mock_setup_entry, async_add_devices, switch_factory
) -> None:
    """Test successful async_setup_entry."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ) as mock_get_entities,
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ) as mock_tis_api,
    ):
        mock_setup_entry.runtime_data.api = mock_tis_api(
            hass=hass, devices_dict=DEVICES_DICT
        )
        await async_setup_entry(hass, mock_setup_entry, async_add_devices)
        mock_get_entities.assert_called_once()
        async_add_devices.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_no_switches(
    hass: HomeAssistant, mock_setup_entry, async_add_devices
) -> None:
    """Test async_setup_entry with no switches."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi(hass=hass, devices_dict=DEVICES_DICT),
        ) as mock_tis_api,
    ):
        mock_setup_entry.runtime_data.api = mock_tis_api
        await async_setup_entry(hass, mock_setup_entry, async_add_devices)
        assert not async_add_devices.called


@pytest.mark.asyncio
async def test_handle_control_response_event(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test the handle control response callback."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch.object(
            MockTISApi,
            "send_packet_with_ack",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        event_data = {
            "device_id": SWITCH_DETAILS["device_id"],
            "channel_number": SWITCH_DETAILS["channel_number"],
            "feedback_type": "control_response",
            "additional_bytes": [1, SWITCH_DETAILS["channel_number"], 100],  # ON
        }
        # await hass.async_("tis_control_event", event_data)
        hass.bus.async_fire(str(SWITCH_DETAILS["device_id"]), event_data)
        state = hass.states.get(SWITCH_DETAILS["unique_id"])
        assert state.state == STATE_ON


@pytest.mark.asyncio
async def test_ignore_irrelevant_control_response_event(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test only responding to events relevant to this entity."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch.object(
            MockTISApi,
            "send_packet_with_ack",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        event_data = {
            "device_id": SWITCH_DETAILS["device_id"],
            "channel_number": SWITCH_DETAILS["channel_number"]
            + 1,  # wrong channel number
            "feedback_type": "control_response",
            "additional_bytes": [
                1,
                SWITCH_DETAILS["channel_number"] + 1,
                1,  # wrong channel number with on state, should not become on
            ],
        }
        # await hass.async_("tis_control_event", event_data)
        hass.bus.async_fire(str(SWITCH_DETAILS["device_id"]), event_data)
        state = hass.states.get(SWITCH_DETAILS["unique_id"])
        assert state.state != STATE_ON


@pytest.mark.asyncio
async def test_binary_feedback_event(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test the handle binary feedback callback."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch.object(
            MockTISApi,
            "send_packet_with_ack",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        event_data = {
            "device_id": SWITCH_DETAILS["device_id"],
            "channel_number": SWITCH_DETAILS["channel_number"],
            "feedback_type": "binary_feedback",
            "additional_bytes": [1, 0, 0],  # OFF
        }
        # await hass.async_("tis_control_event", event_data)
        hass.bus.async_fire(str(SWITCH_DETAILS["device_id"]), event_data)
        state = hass.states.get(SWITCH_DETAILS["unique_id"])
        assert state.state == STATE_OFF


@pytest.mark.asyncio
async def test_ignore_irrelevant_binary_feedback_event(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test only responding to events relevant to this entity."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch.object(
            MockTISApi,
            "send_packet_with_ack",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        event_data = {
            "device_id": SWITCH_DETAILS["device_id"],
            "channel_number": SWITCH_DETAILS["channel_number"]
            + 1,  # wrong channel number
            "feedback_type": "binary_feedback",
            "additional_bytes": [
                1,
                8,  # wrong channel number with on state, should not become on
            ],
        }
        # await hass.async_("tis_control_event", event_data)
        hass.bus.async_fire(str(SWITCH_DETAILS["device_id"]), event_data)
        state = hass.states.get(SWITCH_DETAILS["unique_id"])
        assert state.state != STATE_ON


@pytest.mark.asyncio
async def test_update_feedback_event(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test update feedback handler callback."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        event_data = {
            "device_id": SWITCH_DETAILS["device_id"],
            "channel_number": SWITCH_DETAILS["channel_number"],
            "feedback_type": "update_response",
            "additional_bytes": [1, 1],  # correct channel ON
        }
        # await hass.async_("tis_control_event", event_data)
        hass.bus.async_fire(str(SWITCH_DETAILS["device_id"]), event_data)
        state = hass.states.get(SWITCH_DETAILS["unique_id"])
        assert state.state == STATE_ON


@pytest.mark.asyncio
async def test_ignore_irrelevant_update_feedback_event(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test only responding to events relevant to this entity."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        event_data = {
            "device_id": SWITCH_DETAILS["device_id"],
            "channel_number": SWITCH_DETAILS["channel_number"],
            "feedback_type": "update_response",
            "additional_bytes": [1, 0, 1],  # wrong channel ON
        }
        # await hass.async_("tis_control_event", event_data)
        hass.bus.async_fire(str(SWITCH_DETAILS["device_id"]), event_data)
        state = hass.states.get(SWITCH_DETAILS["unique_id"])
        assert state.state != STATE_ON


@pytest.mark.asyncio
async def test_async_turn_on_no_feedback(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test async turn on without device feedback which should not update the state."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        entity = next(
            (
                ent
                for ent in hass.data["switch"].entities
                if ent.entity_id == SWITCH_DETAILS["unique_id"]
            ),
            None,
        )
        assert entity is not None
        await entity.async_turn_on()
        state = hass.states.get(SWITCH_DETAILS["unique_id"])
        assert state.state != STATE_ON


@pytest.mark.asyncio
async def test_async_turn_on_with_feedback(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test async turn on with device feedback."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch.object(
            MockTISApi,
            "send_packet_with_ack",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        entity = next(
            (
                ent
                for ent in hass.data["switch"].entities
                if ent.entity_id == SWITCH_DETAILS["unique_id"]
            ),
            None,
        )
        assert entity is not None
        await entity.async_turn_on()
        assert entity.state == STATE_ON


@pytest.mark.asyncio
async def test_async_turn_off_with_feedback(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test async turn off with device feedback."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch.object(
            MockTISApi,
            "send_packet_with_ack",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        entity = next(
            (
                ent
                for ent in hass.data["switch"].entities
                if ent.entity_id == SWITCH_DETAILS["unique_id"]
            ),
            None,
        )
        assert entity is not None
        await entity.async_turn_off()
        assert entity.state == STATE_OFF


@pytest.mark.asyncio
async def test_async_turn_off_no_feedback(
    hass: HomeAssistant, mock_config_entry, switch_factory
) -> None:
    """Test async turn off without device feedback which should not update the state."""
    with (
        patch.object(
            MockTISApi,
            "get_entities",
            new_callable=AsyncMock,
            return_value=switch_factory(**SWITCH_DETAILS),
        ),
        patch(
            "homeassistant.components.tis_control.TISApi",
            new=MockTISApi,
        ),
        patch.object(
            MockTISApi,
            "send_packet_with_ack",
            new_callable=AsyncMock,
        ) as mock_send_packet_with_ack,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        entity = next(
            (
                ent
                for ent in hass.data["switch"].entities
                if ent.entity_id == SWITCH_DETAILS["unique_id"]
            ),
            None,
        )
        assert entity is not None
        # turn switch on because it's off by default
        mock_send_packet_with_ack.return_value = True
        await entity.async_turn_on()
        mock_send_packet_with_ack.return_value = False
        await entity.async_turn_off()
        assert entity.state != STATE_OFF
