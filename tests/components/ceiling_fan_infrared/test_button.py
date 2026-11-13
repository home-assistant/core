"""Tests for the Ceiling Fan Infrared button platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.ceiling_fan import GenericCeilingFanCode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def button_only() -> Generator[None]:
    """Enable only the button platform."""
    with patch(
        "homeassistant.components.ceiling_fan_infrared.PLATFORMS",
        [Platform.BUTTON],
    ):
        yield


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of the button platform."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


_BUTTON_PRESSES = [
    ("brightness_up", GenericCeilingFanCode.LIGHT_BRIGHTNESS_UP),
    ("brightness_down", GenericCeilingFanCode.LIGHT_BRIGHTNESS_DOWN),
    ("color_warmer", GenericCeilingFanCode.LIGHT_COLOR_WARMER),
    ("color_cooler", GenericCeilingFanCode.LIGHT_COLOR_COOLER),
]


@pytest.mark.parametrize(("key", "expected_code"), _BUTTON_PRESSES)
@pytest.mark.usefixtures("infrared_codes")
async def test_button_press(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
    key: str,
    expected_code: GenericCeilingFanCode,
) -> None:
    """Test each button sends its command."""
    config_entry = MockConfigEntry(
        domain="ceiling_fan_infrared",
        title="Ceiling fan via Test IR emitter",
        entry_id="1234567890",
        data={"infrared_entity_id": "infrared.test_ir_emitter"},
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, "ceiling_fan_infrared", f"{config_entry.entry_id}_{key}"
    )
    assert entity_id is not None

    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {CommonServiceArgument.ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]
