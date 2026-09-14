"""Tests for the Novy Hood light platform."""

import pytest
from rf_protocols.codes.novy.cooker_hood import NovyCookerHoodButton

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import TRANSMITTER_ENTITY_ID

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.common import assert_availability_follows_source_entity
from tests.components.radio_frequency.common import MockRadioFrequencyEntity

ENTITY_ID = "light.novy_cooker_hood_light"


@pytest.mark.usefixtures("init_novy_cooker_hood")
async def test_turn_on_and_off_send_light_once_each(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
) -> None:
    """Turn on sends a light toggle and flips is_on; turn off does the same."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    context = Context()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        context=context,
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.context is context
    assert len(mock_rf_entity.send_command_calls) == 1
    assert mock_rf_entity.send_command_calls[0].context is context

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        context=context,
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert len(mock_rf_entity.send_command_calls) == 2
    assert [c.command.key for c in mock_rf_entity.send_command_calls] == [
        NovyCookerHoodButton.LIGHT.code,
        NovyCookerHoodButton.LIGHT.code,
    ]


async def test_restore_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light restores its previous on state."""
    mock_restore_cache(hass, [State(ENTITY_ID, STATE_ON)])
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("mock_rf_entity", "init_novy_cooker_hood")
async def test_entity_follows_transmitter_availability(
    hass: HomeAssistant,
) -> None:
    """The light becomes unavailable when the transmitter does, and back."""
    await assert_availability_follows_source_entity(
        hass, ENTITY_ID, TRANSMITTER_ENTITY_ID
    )


async def test_tracking_follows_transmitter_rename(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_cooker_hood: MockConfigEntry,
) -> None:
    """Availability tracking and sending survive a transmitter entity rename."""
    new_transmitter_id = "radio_frequency.renamed_transmitter"
    entity_registry.async_update_entity(
        TRANSMITTER_ENTITY_ID, new_entity_id=new_transmitter_id
    )
    await hass.async_block_till_done()

    await assert_availability_follows_source_entity(hass, ENTITY_ID, new_transmitter_id)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert len(mock_rf_entity.send_command_calls) == 1
