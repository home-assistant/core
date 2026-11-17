"""Test the Infrared button platform."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.infrared_button.const import (
    CONF_MODULATION,
    CONF_TIMINGS,
    DOMAIN,
    SUBENTRY_TYPE_COMMAND,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import TIMINGS

ENTITY_ID = "button.living_room_tv_power"


async def test_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test pressing the button sends the learned timings through the emitter."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.config_subentry_id == "power_subentry"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert entity_entry.device_id == device.id

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert command.get_raw_timings() == TIMINGS
    assert command.modulation == 38000


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_add_command(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a new command gets a button without a restart."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_COMMAND,
            title="Volume up",
            data={CONF_TIMINGS: TIMINGS, CONF_MODULATION: 38000},
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()

    assert hass.states.get("button.living_room_tv_volume_up") is not None
