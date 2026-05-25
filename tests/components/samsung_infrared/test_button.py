"""Tests for the Samsung Infrared button platform."""

from infrared_protocols.codes.samsung.tv import SamsungTVCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test button entities are created with correct attributes."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Snapshot the full set of created entities to avoid a brittle hard-coded count
    assert sorted(entry.entity_id for entry in entity_entries) == snapshot(
        name="entity_ids"
    )

    # Verify all entities belong to the same device
    device_entry = device_registry.async_get_device(
        identifiers={("samsung_infrared", mock_config_entry.entry_id)}
    )
    assert device_entry
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id
        assert entity_entry.domain == BUTTON_DOMAIN
        assert entity_entry.has_entity_name is True
        assert entity_entry.platform == "samsung_infrared"

    # Snapshot a representative subset to verify structure
    representative_entities = [
        "button.samsung_tv_source",
        "button.samsung_tv_number_5",
        "button.samsung_tv_red",
    ]
    for entity_id in representative_entities:
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry == snapshot(name=f"{entity_id}-entry")
        state = hass.states.get(entity_id)
        assert state == snapshot(name=f"{entity_id}-state")


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.samsung_tv_power", SamsungTVCode.POWER),
        ("button.samsung_tv_source", SamsungTVCode.SOURCE),
        ("button.samsung_tv_settings", SamsungTVCode.SETTINGS),
        ("button.samsung_tv_info", SamsungTVCode.INFO),
        ("button.samsung_tv_exit", SamsungTVCode.EXIT),
        ("button.samsung_tv_return", SamsungTVCode.RETURN),
        ("button.samsung_tv_home", SamsungTVCode.HOME),
        ("button.samsung_tv_red", SamsungTVCode.RED),
        ("button.samsung_tv_green", SamsungTVCode.GREEN),
        ("button.samsung_tv_yellow", SamsungTVCode.YELLOW),
        ("button.samsung_tv_blue", SamsungTVCode.BLUE),
        ("button.samsung_tv_up", SamsungTVCode.NAV_UP),
        ("button.samsung_tv_down", SamsungTVCode.NAV_DOWN),
        ("button.samsung_tv_left", SamsungTVCode.NAV_LEFT),
        ("button.samsung_tv_right", SamsungTVCode.NAV_RIGHT),
        ("button.samsung_tv_ok", SamsungTVCode.OK),
        ("button.samsung_tv_previous_channel", SamsungTVCode.PREVIOUS_CHANNEL),
        ("button.samsung_tv_number_0", SamsungTVCode.NUM_0),
        ("button.samsung_tv_number_1", SamsungTVCode.NUM_1),
        ("button.samsung_tv_number_2", SamsungTVCode.NUM_2),
        ("button.samsung_tv_number_3", SamsungTVCode.NUM_3),
        ("button.samsung_tv_number_4", SamsungTVCode.NUM_4),
        ("button.samsung_tv_number_5", SamsungTVCode.NUM_5),
        ("button.samsung_tv_number_6", SamsungTVCode.NUM_6),
        ("button.samsung_tv_number_7", SamsungTVCode.NUM_7),
        ("button.samsung_tv_number_8", SamsungTVCode.NUM_8),
        ("button.samsung_tv_number_9", SamsungTVCode.NUM_9),
        ("button.samsung_tv_fast_forward", SamsungTVCode.FAST_FORWARD),
        ("button.samsung_tv_rewind", SamsungTVCode.REWIND),
        ("button.samsung_tv_record", SamsungTVCode.RECORD),
        ("button.samsung_tv_tools", SamsungTVCode.TOOLS),
        ("button.samsung_tv_browser", SamsungTVCode.BROWSER),
        ("button.samsung_tv_ad_subtitle", SamsungTVCode.AD_SUBTITLE),
        ("button.samsung_tv_e_manual", SamsungTVCode.E_MANUAL),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: SamsungTVCode,
) -> None:
    """Test pressing each button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert (
        mock_infrared_emitter_entity.send_command_calls[0] == expected_code.to_command()
    )


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test button becomes unavailable when IR entity is unavailable."""
    entity_id = "button.samsung_tv_source"
    await assert_availability_follows_source_entity(hass, entity_id, EMITTER_ENTITY_ID)
