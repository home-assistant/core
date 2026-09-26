"""Tests for the Alpha Bidet Infrared button platform."""

from infrared_protocols.codes.alpha_bidet.jx2 import AlphaBidetJX2Code
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alpha_bidet_infrared.const import DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
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
    """Test all button entities are created with the correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry == snapshot(name="device")
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ):
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.alpha_bidet_jx2_stop", AlphaBidetJX2Code.STOP),
        ("button.alpha_bidet_jx2_stop_hold", AlphaBidetJX2Code.STOP_HOLD),
        ("button.alpha_bidet_jx2_rear", AlphaBidetJX2Code.REAR),
        ("button.alpha_bidet_jx2_front", AlphaBidetJX2Code.FRONT),
        ("button.alpha_bidet_jx2_dry", AlphaBidetJX2Code.DRY),
        ("button.alpha_bidet_jx2_wash_and_dry", AlphaBidetJX2Code.WASH_AND_DRY),
        ("button.alpha_bidet_jx2_easy_wash", AlphaBidetJX2Code.EASY_WASH),
        ("button.alpha_bidet_jx2_water_dry_up", AlphaBidetJX2Code.WATER_DRY_UP),
        ("button.alpha_bidet_jx2_water_dry_down", AlphaBidetJX2Code.WATER_DRY_DOWN),
        ("button.alpha_bidet_jx2_nozzle_up", AlphaBidetJX2Code.NOZZLE_UP),
        ("button.alpha_bidet_jx2_nozzle_down", AlphaBidetJX2Code.NOZZLE_DOWN),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: AlphaBidetJX2Code,
) -> None:
    """Test pressing a button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_code.to_command().get_raw_timings()


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test a button becomes unavailable when the IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, "button.alpha_bidet_jx2_stop", MOCK_INFRARED_EMITTER_ENTITY_ID
    )
