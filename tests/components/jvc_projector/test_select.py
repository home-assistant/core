"""Tests for JVC Projector select platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from jvcprojector import command as cmd

from homeassistant.components.jvc_projector.coordinator import INTERVAL_FAST
from homeassistant.components.select import (
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed

INPUT_ENTITY_ID = "select.jvc_projector_input"
HDR_PROCESSING_ENTITY_ID = "select.jvc_projector_hdr_processing"
HDR_SENSOR_ENTITY_ID = "sensor.jvc_projector_hdr"


async def test_input_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test input select."""
    entity = hass.states.get(INPUT_ENTITY_ID)
    assert entity
    assert entity.attributes.get(ATTR_FRIENDLY_NAME) == "JVC Projector Input"
    assert entity.attributes.get(ATTR_OPTIONS) == [cmd.Input.HDMI1, cmd.Input.HDMI2]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: INPUT_ENTITY_ID,
            ATTR_OPTION: cmd.Input.HDMI2,
        },
        blocking=True,
    )
    mock_device.set.assert_called_once_with(cmd.Input, cmd.Input.HDMI2)


async def test_enable_hdr_processing_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test enabling the HDR processing select (disabled by default)."""
    entry = entity_registry.async_get(HDR_PROCESSING_ENTITY_ID)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    hdr_sensor_entry = entity_registry.async_get(HDR_SENSOR_ENTITY_ID)
    assert hdr_sensor_entry is not None
    assert hdr_sensor_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    entity_registry.async_update_entity(HDR_SENSOR_ENTITY_ID, disabled_by=None)
    entity_registry.async_update_entity(HDR_PROCESSING_ENTITY_ID, disabled_by=None)
    await hass.config_entries.async_reload(mock_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(HDR_PROCESSING_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"

    freezer.tick(timedelta(seconds=INTERVAL_FAST.seconds + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(HDR_PROCESSING_ENTITY_ID)
    assert state is not None
    assert state.state == "static"

    freezer.tick(timedelta(seconds=INTERVAL_FAST.seconds + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(HDR_PROCESSING_ENTITY_ID)
    assert state is not None
    assert state.state == "static"
