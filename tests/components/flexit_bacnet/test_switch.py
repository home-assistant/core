"""Tests for the Flexit Nordic (BACnet) switch entities."""

from unittest.mock import AsyncMock

from flexit_bacnet import DecodingError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.flexit_bacnet import setup_with_selected_platforms

ENTITY_ID = "switch.device_name_electric_heater"


async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch states are correctly collected from library."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_switches_implementation(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the switch can be turned on and off."""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SWITCH])
    assert hass.states.get(ENTITY_ID) == snapshot(name=f"{ENTITY_ID}-state")

    # Set to off
    mock_flexit_bacnet.electric_heater = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mocked_method = getattr(mock_flexit_bacnet, "disable_electric_heater")
    assert len(mocked_method.mock_calls) == 1
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # Set to on
    mock_flexit_bacnet.electric_heater = True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mocked_method = getattr(mock_flexit_bacnet, "enable_electric_heater")
    assert len(mocked_method.mock_calls) == 1
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # Error recovery, when turning off
    mock_flexit_bacnet.disable_electric_heater.side_effect = DecodingError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mocked_method = getattr(mock_flexit_bacnet, "disable_electric_heater")
    assert len(mocked_method.mock_calls) == 2

    mock_flexit_bacnet.disable_electric_heater.side_effect = None
    mock_flexit_bacnet.electric_heater = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    # Error recovery, when turning on
    mock_flexit_bacnet.enable_electric_heater.side_effect = DecodingError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mocked_method = getattr(mock_flexit_bacnet, "enable_electric_heater")
    assert len(mocked_method.mock_calls) == 2

    mock_flexit_bacnet.enable_electric_heater.side_effect = None
    mock_flexit_bacnet.electric_heater = True

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == STATE_ON
