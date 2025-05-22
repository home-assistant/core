"""Test switch platform for Swing2Sleep Smarla integration."""

from pysmarlaapi.federwiege.classes import Property
import pytest

from homeassistant.components.smarla.switch import SWITCHES
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntityDescription,
)
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

from .common import get_entity_id_by_unique_id

from tests.common import MockConfigEntry


@pytest.mark.parametrize("switch_desc", SWITCHES)
async def test_switch_behavior(
    hass: HomeAssistant,
    switch_desc: SwitchEntityDescription,
    mock_config_entry: MockConfigEntry,
    mock_connection,
    mock_federwiege,
) -> None:
    """Test SmarlaSwitch on/off behavior."""
    # Assign switch property to federwiege
    mock_property = Property[bool](None, False)
    mock_federwiege.get_property.return_value = mock_property
    # Add the mock entry to hass
    mock_config_entry.add_to_hass(hass)

    # Set up the platform
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get entity id by unique id
    unique_id = f"{mock_federwiege.serial_number}-{switch_desc.key}"
    entity_id = get_entity_id_by_unique_id(hass, Platform.SWITCH, unique_id)
    assert entity_id is not None

    # Check entity initial state
    assert hass.states.get(entity_id).state == STATE_OFF

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_property.set(True, push=False)
    await mock_property.notify_listeners()
    assert hass.states.get(entity_id).state == STATE_ON

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_property.set(False, push=False)
    await mock_property.notify_listeners()
    assert hass.states.get(entity_id).state == STATE_OFF
