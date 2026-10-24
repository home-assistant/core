"""Tests for the OSRAM infrared remote buttons."""

from unittest.mock import patch

from infrared_protocols.codes.osram.light import OSRAM_ADDRESS, OsramLightCode
from infrared_protocols.commands.nec import NECCommand
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.osram_infrared.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

ENABLED_CODES = {
    OsramLightCode.BRIGHTNESS_UP,
    OsramLightCode.BRIGHTNESS_DOWN,
}


@pytest.fixture
def mock_osram_light_code_to_command() -> None:
    """Use real NEC commands for button transmission tests."""


@pytest.mark.parametrize("has_receiver_entity", [False, True])
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Register every remote button, with only brightness controls enabled."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    buttons = [entry for entry in entries if entry.domain == BUTTON_DOMAIN]
    assert len(buttons) == 24
    assert {entry.unique_id for entry in buttons} == {
        f"{mock_config_entry.entry_id}_{code.name.lower()}" for code in OsramLightCode
    }
    assert {entry.unique_id for entry in buttons if entry.disabled_by is None} == {
        f"{mock_config_entry.entry_id}_{code.name.lower()}" for code in ENABLED_CODES
    }
    assert {
        entry.disabled_by for entry in buttons if entry.disabled_by is not None
    } == {er.RegistryEntryDisabler.INTEGRATION}
    assert {entry.device_id for entry in entries} == {buttons[0].device_id}
    assert {
        entry.entity_id: {
            "unique_id": entry.unique_id,
            "name": entry.original_name,
            "translation_key": entry.translation_key,
            "disabled_by": entry.disabled_by,
        }
        for entry in buttons
    } == snapshot
    assert {state.entity_id for state in hass.states.async_all(BUTTON_DOMAIN)} == {
        "button.osram_light_brightness_up",
        "button.osram_light_brightness_down",
    }


@pytest.mark.parametrize("code", list(OsramLightCode))
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_press_sends_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    code: OsramLightCode,
) -> None:
    """Each button sends exactly one complete NEC command with the light unknown."""
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_{code.name.lower()}"
    )
    light_state = hass.states.get("light.osram_light")
    assert light_state
    assert light_state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert isinstance(command, NECCommand)
    assert command.address == OSRAM_ADDRESS
    assert command.command == code.value
    assert command.repeat_count == 0
    assert command.modulation == 38000
    assert command.get_raw_timings() == code.to_command().get_raw_timings()
    assert hass.states.get("light.osram_light") == light_state


@pytest.mark.parametrize("code", list(OsramLightCode))
@pytest.mark.parametrize("light_service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_press_independent_of_light_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    code: OsramLightCode,
    light_service: str,
) -> None:
    """Send remote commands while the light is on or off without updating it."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        light_service,
        {ATTR_ENTITY_ID: "light.osram_light"},
        blocking=True,
    )
    light_state = hass.states.get("light.osram_light")
    mock_infrared_emitter_entity.send_command_calls.clear()
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_{code.name.lower()}"
    )

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert isinstance(command, NECCommand)
    assert command.command == code.value
    assert hass.states.get("light.osram_light") == light_state


@pytest.mark.parametrize("code", sorted(set(OsramLightCode) - ENABLED_CODES))
@pytest.mark.usefixtures("init_integration")
async def test_enable_button(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    code: OsramLightCode,
) -> None:
    """Users can enable any additional button individually through the registry."""
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_{code.name.lower()}"
    )
    assert entity_id
    assert hass.states.get(entity_id) is None
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert isinstance(command, NECCommand)
    assert command.command == code.value
    assert len(hass.states.async_all(BUTTON_DOMAIN)) == 3


@pytest.mark.parametrize(
    ("disabled_by", "enabled"),
    [(None, True), (er.RegistryEntryDisabler.USER, False)],
)
async def test_existing_entities_preserved(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    disabled_by: er.RegistryEntryDisabler | None,
    enabled: bool,
) -> None:
    """Keep the light ID and user-customized Mode entity through setup and reload."""
    mock_config_entry.add_to_hass(hass)
    light = entity_registry.async_get_or_create(
        LIGHT_DOMAIN,
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        suggested_object_id="existing_osram_light",
        disabled_by=disabled_by,
    )
    mode = entity_registry.async_get_or_create(
        BUTTON_DOMAIN,
        DOMAIN,
        f"{mock_config_entry.entry_id}_mode",
        config_entry=mock_config_entry,
        suggested_object_id="custom_osram_mode",
        disabled_by=disabled_by,
    )
    entity_registry.async_update_entity(mode.entity_id, name="My mode button")
    original_data = mock_config_entry.data.copy()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.data == original_data
    assert (hass.states.get(light.entity_id) is not None) is enabled
    light_entry = entity_registry.async_get(light.entity_id)
    assert light_entry
    assert light_entry.id == light.id
    assert light_entry.disabled_by is disabled_by
    mode_entry = entity_registry.async_get(mode.entity_id)
    assert mode_entry
    assert mode_entry.id == mode.id
    assert mode_entry.name == "My mode button"
    assert mode_entry.disabled_by is disabled_by
    assert (hass.states.get(mode.entity_id) is not None) is enabled
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 25
    assert len([entry for entry in entries if entry.unique_id.endswith("_mode")]) == 1
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.osram_light_brightness_up"},
        blocking=True,
    )
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert isinstance(command, NECCommand)
    assert command.command == OsramLightCode.BRIGHTNESS_UP


@pytest.mark.parametrize(
    "entity_id",
    [
        "button.osram_light_brightness_up",
        "button.osram_light_brightness_down",
        "button.osram_light_mode",
    ],
)
@pytest.mark.parametrize("has_receiver_entity", [False, True])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_availability(hass: HomeAssistant, entity_id: str) -> None:
    """Button availability follows the emitter, independently of the receiver."""
    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    await assert_availability_follows_source_entity(
        hass, entity_id, [EMITTER_ENTITY_ID]
    )


@pytest.mark.parametrize("platforms", [[Platform.BUTTON]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_press_without_light(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Buttons work without loading the light platform."""
    assert hass.states.get("light.osram_light") is None
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.osram_light_mode"},
        blocking=True,
    )
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert isinstance(command, NECCommand)
    assert command.command == OsramLightCode.MODE


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_transmission_failure(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Surface emitter failures through the button action."""
    with (
        patch.object(
            mock_infrared_emitter_entity,
            "async_send_command",
            side_effect=HomeAssistantError("Transmission failed"),
        ),
        pytest.raises(HomeAssistantError, match="Transmission failed"),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.osram_light_mode"},
            blocking=True,
        )
