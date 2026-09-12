"""Tests for the Somfy RTS cover platform."""

import pytest

from rf_protocols import SomfyRTSButton, SomfyRTSCommand

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

from homeassistant.components.somfy_rts.const import DOMAIN

from .conftest import ADDRESS, COVER_ENTITY_ID, TRANSMITTER_ENTITY_ID


async def test_missing_storage_defaults_rolling_code(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that absent storage does not crash setup and defaults the rolling code."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_rf_entity.send_command_calls) == 1
    assert mock_rf_entity.send_command_calls[0].command.rolling_code >= 1


@pytest.mark.parametrize(
    "stored_data",
    [{}, {"other_key": 99}],
)
async def test_corrupt_storage_defaults_rolling_code(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict,
    stored_data: dict,
) -> None:
    """Test that corrupt storage data does not crash setup and defaults the rolling code."""
    hass_storage[f"{DOMAIN}/{mock_config_entry.entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}/{mock_config_entry.entry_id}",
        "data": stored_data,
    }

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_rf_entity.send_command_calls) == 1
    assert mock_rf_entity.send_command_calls[0].command.rolling_code >= 1


async def test_initial_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
) -> None:
    """Test the cover is set up with correct initial attributes."""
    state = hass.states.get(COVER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.mark.parametrize(
    ("service", "expected_button"),
    [
        (SERVICE_OPEN_COVER, SomfyRTSButton.UP),
        (SERVICE_CLOSE_COVER, SomfyRTSButton.DOWN),
        (SERVICE_STOP_COVER, SomfyRTSButton.MY),
    ],
)
async def test_cover_service_sends_command(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
    service: str,
    expected_button: SomfyRTSButton,
) -> None:
    """Test each cover service sends an RF command with the correct button."""
    context = Context()
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        context=context,
        blocking=True,
    )

    assert len(mock_rf_entity.send_command_calls) == 1
    sent = mock_rf_entity.send_command_calls[0]
    assert isinstance(sent.command, SomfyRTSCommand)
    assert sent.command.button == expected_button
    assert sent.command.address == ADDRESS
    assert sent.command.frame_repeats == 3
    assert sent.context is context


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        (SERVICE_OPEN_COVER, STATE_OPEN),
        (SERVICE_CLOSE_COVER, STATE_CLOSED),
    ],
)
async def test_cover_state_after_command(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
    service: str,
    expected_state: str,
) -> None:
    """Test the cover state is updated optimistically after open and close."""
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(COVER_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


async def test_rolling_code_increments(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
) -> None:
    """Test that each command uses a strictly incrementing rolling code."""
    for service in (SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER, SERVICE_STOP_COVER):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: COVER_ENTITY_ID},
            blocking=True,
        )

    codes = [call.command.rolling_code for call in mock_rf_entity.send_command_calls]
    assert codes == sorted(codes)
    assert len(set(codes)) == 3


async def test_rolling_code_persisted(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
    hass_storage: dict,
) -> None:
    """Test that the rolling code is saved to storage after each command."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: COVER_ENTITY_ID},
        blocking=True,
    )

    entry_id = init_integration.entry_id
    stored = hass_storage[f"somfy_rts/{entry_id}"]
    assert stored["data"]["rolling_code"] == mock_rf_entity.send_command_calls[0].command.rolling_code


async def test_restore_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the cover restores its last known state on startup."""
    mock_restore_cache(hass, [State(COVER_ENTITY_ID, STATE_OPEN)])
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OPEN


async def test_transmitter_unavailable(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
) -> None:
    """Test the cover becomes unavailable when the transmitter goes unavailable."""
    hass.states.async_set(TRANSMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_transmitter_becomes_available(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
) -> None:
    """Test the cover recovers when the transmitter becomes available again."""
    hass.states.async_set(TRANSMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(TRANSMITTER_ENTITY_ID, "on")
    await hass.async_block_till_done()

    state = hass.states.get(COVER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the config entry removes the entity."""
    assert hass.states.get(COVER_ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
