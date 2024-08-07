"""Tests for the pyLoad Switches."""

from collections.abc import Generator
from unittest.mock import AsyncMock, call, patch

from pyloadapi import CannotConnect, InvalidAuth
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pyload.switch import PyLoadSwitch
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

# Maps entity to the mock calls to assert
API_CALL = {
    PyLoadSwitch.PAUSE_RESUME_QUEUE: {
        SERVICE_TURN_ON: call.unpause,
        SERVICE_TURN_OFF: call.pause,
        SERVICE_TOGGLE: call.toggle_pause,
    },
    PyLoadSwitch.RECONNECT: {
        SERVICE_TURN_ON: call.toggle_reconnect,
        SERVICE_TURN_OFF: call.toggle_reconnect,
        SERVICE_TOGGLE: call.toggle_reconnect,
    },
}


@pytest.fixture(autouse=True)
def switch_only() -> Generator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.pyload.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


async def test_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test switch state."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("service_call"),
    [
        SERVICE_TURN_ON,
        SERVICE_TURN_OFF,
        SERVICE_TOGGLE,
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
    service_call: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch turn on/off, toggle method."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    for entity_entry in entity_entries:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service_call,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )
        assert (
            API_CALL[entity_entry.translation_key][service_call]
            in mock_pyloadapi.method_calls
        )
        mock_pyloadapi.reset_mock()


@pytest.mark.parametrize(
    ("service_call"),
    [
        SERVICE_TURN_ON,
        SERVICE_TURN_OFF,
        SERVICE_TOGGLE,
    ],
)
@pytest.mark.parametrize(
    ("side_effect"),
    [CannotConnect, InvalidAuth],
)
async def test_turn_on_off_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
    service_call: str,
    entity_registry: er.EntityRegistry,
    side_effect: Exception,
) -> None:
    """Test switch turn on/off, toggle method."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    mock_pyloadapi.unpause.side_effect = side_effect
    mock_pyloadapi.pause.side_effect = side_effect
    mock_pyloadapi.toggle_pause.side_effect = side_effect
    mock_pyloadapi.toggle_reconnect.side_effect = side_effect

    for entity_entry in entity_entries:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                service_call,
                {ATTR_ENTITY_ID: entity_entry.entity_id},
                blocking=True,
            )
