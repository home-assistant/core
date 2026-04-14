"""Test Subaru select."""

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.subaru.const import (
    VEHICLE_HAS_EV,
    VEHICLE_HAS_REMOTE_START,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api_responses import TEST_VIN_2_EV, TEST_VIN_3_G3, VEHICLE_DATA
from .conftest import setup_subaru_config_entry

from tests.common import MockConfigEntry

ENTITY_ID = "select.test_vehicle_2_climate_preset"


async def test_device_exists(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ev_entry: MockConfigEntry,
) -> None:
    """Test subaru select entity exists."""
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry


async def test_select_option(
    hass: HomeAssistant,
    ev_entry: MockConfigEntry,
) -> None:
    """Test subaru select updates state and runtime_data."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "Full Heat"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "Full Heat"
    assert ev_entry.runtime_data.climate_presets[TEST_VIN_2_EV] == "Full Heat"


async def test_restore_state(
    hass: HomeAssistant,
    ev_entry_with_saved_climate: MockConfigEntry,
) -> None:
    """Test subaru select restores previous state on startup."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == "Full Heat"
    assert (
        ev_entry_with_saved_climate.runtime_data.climate_presets[TEST_VIN_2_EV]
        == "Full Heat"
    )


async def test_no_select_without_remote_start(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    subaru_config_entry: MockConfigEntry,
) -> None:
    """Test no select created for vehicle without remote start or EV."""
    vehicle_data = {
        **VEHICLE_DATA[TEST_VIN_3_G3],
        VEHICLE_HAS_REMOTE_START: False,
        VEHICLE_HAS_EV: False,
    }
    await setup_subaru_config_entry(
        hass,
        subaru_config_entry,
        vehicle_list=[TEST_VIN_3_G3],
        vehicle_data=vehicle_data,
    )
    entry = entity_registry.async_get("select.test_vehicle_3_climate_preset")
    assert entry is None
