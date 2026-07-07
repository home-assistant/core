"""Tests for the Edifier Infrared button platform."""

from infrared_protocols.codes.edifier.r1700bt import EdifierR1700BTCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity

BLUETOOTH_BUTTON_ENTITY_ID = "button.edifier_r1700bt_bluetooth"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the button entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.edifier_r1700bt_bluetooth", EdifierR1700BTCode.BLUETOOTH),
        ("button.edifier_r1700bt_line_1", EdifierR1700BTCode.LINE_1),
        ("button.edifier_r1700bt_line_2", EdifierR1700BTCode.LINE_2),
        ("button.edifier_r1700bt_fx_on", EdifierR1700BTCode.FX_ON),
        ("button.edifier_r1700bt_fx_off", EdifierR1700BTCode.FX_OFF),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: EdifierR1700BTCode,
) -> None:
    """Test each button press sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0] == expected_code


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test button becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, BLUETOOTH_BUTTON_ENTITY_ID, EMITTER_ENTITY_ID
    )
