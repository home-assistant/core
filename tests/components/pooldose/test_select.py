"""Tests for the Seko PoolDose select platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pooldose.request_status import RequestStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    Platform,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SELECT]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_all_selects(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Pooldose select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_entity_unavailable_no_coordinator_data(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select entity becomes unavailable when coordinator has no data."""
    # Verify entity has a state initially
    water_meter_state = hass.states.get("select.pool_device_water_meter_unit")
    assert water_meter_state.state == UnitOfVolume.CUBIC_METERS

    # Update coordinator data to None
    mock_pooldose_client.instant_values_structured.return_value = (None, None)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check entity becomes unavailable
    water_meter_state = hass.states.get("select.pool_device_water_meter_unit")
    assert water_meter_state.state == "unavailable"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_state_changes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_pooldose_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select state changes when coordinator updates."""
    # Initial state
    ph_method_state = hass.states.get("select.pool_device_ph_dosing_method")
    assert ph_method_state.state == "proportional"

    # Update coordinator data with select value changed
    current_data = mock_pooldose_client.instant_values_structured.return_value[1]
    updated_data = current_data.copy()
    updated_data["select"]["ph_type_dosing_method"]["value"] = "timed"

    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        updated_data,
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check state changed
    ph_method_state = hass.states.get("select.pool_device_ph_dosing_method")
    assert ph_method_state.state == "timed"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_option_unit_conversion(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test selecting an option with unit conversion (HA unit -> API value)."""
    # Verify initial state is m³ (displayed as Unicode)
    water_meter_state = hass.states.get("select.pool_device_water_meter_unit")
    assert water_meter_state.state == UnitOfVolume.CUBIC_METERS

    # Select Liters option
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: "select.pool_device_water_meter_unit",
            ATTR_OPTION: UnitOfVolume.LITERS,
        },
        blocking=True,
    )

    # Verify API was called with "L" (not Unicode)
    mock_pooldose_client.set_select.assert_called_once_with("water_meter_unit", "L")

    # Verify state updated to L (Unicode)
    water_meter_state = hass.states.get("select.pool_device_water_meter_unit")
    assert water_meter_state.state == UnitOfVolume.LITERS


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_option_flow_rate_unit_conversion(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test selecting flow rate unit with conversion."""
    # Verify initial state
    flow_rate_state = hass.states.get("select.pool_device_flow_rate_unit")
    assert flow_rate_state.state == UnitOfVolumeFlowRate.LITERS_PER_SECOND

    # Select cubic meters per hour
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: "select.pool_device_flow_rate_unit",
            ATTR_OPTION: UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        },
        blocking=True,
    )

    # Verify API was called with "m3/h" (not Unicode m³/h)
    mock_pooldose_client.set_select.assert_called_once_with("flow_rate_unit", "m3/h")

    # Verify state updated to m³/h (with Unicode)
    flow_rate_state = hass.states.get("select.pool_device_flow_rate_unit")
    assert flow_rate_state.state == UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR


@pytest.mark.usefixtures("init_integration")
async def test_select_option_no_conversion(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test selecting an option without unit conversion."""
    # Verify initial state
    ph_set_state = hass.states.get("select.pool_device_ph_dosing_set")
    assert ph_set_state.state == "acid"

    # Select alkaline option
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: "select.pool_device_ph_dosing_set",
            ATTR_OPTION: "alcalyne",
        },
        blocking=True,
    )

    # Verify API was called with exact value
    mock_pooldose_client.set_select.assert_called_once_with(
        "ph_type_dosing_set", "alcalyne"
    )

    # Verify state updated
    ph_set_state = hass.states.get("select.pool_device_ph_dosing_set")
    assert ph_set_state.state == "alcalyne"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_dosing_method_options(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test selecting different dosing method options."""
    # Test ORP dosing method
    orp_method_state = hass.states.get("select.pool_device_orp_dosing_method")
    assert orp_method_state.state == "on_off"

    # Change to proportional
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: "select.pool_device_orp_dosing_method",
            ATTR_OPTION: "proportional",
        },
        blocking=True,
    )

    # Verify API call
    mock_pooldose_client.set_select.assert_called_once_with(
        "orp_type_dosing_method", "proportional"
    )

    # Verify state
    orp_method_state = hass.states.get("select.pool_device_orp_dosing_method")
    assert orp_method_state.state == "proportional"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_dosing_set_high_low(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
) -> None:
    """Test selecting high/low dosing intensity."""
    # Chlorine dosing set starts as high in fixture
    cl_set_state = hass.states.get("select.pool_device_chlorine_dosing_set")
    assert cl_set_state.state == "high"

    # Change to low
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {
            ATTR_ENTITY_ID: "select.pool_device_chlorine_dosing_set",
            ATTR_OPTION: "low",
        },
        blocking=True,
    )

    # Verify API call
    mock_pooldose_client.set_select.assert_called_once_with("cl_type_dosing_set", "low")

    # Verify state
    cl_set_state = hass.states.get("select.pool_device_chlorine_dosing_set")
    assert cl_set_state.state == "low"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_actions_cannot_connect_select(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """When the client write method raises, ServiceValidationError('cannot_connect') is raised."""
    client = mock_pooldose_client
    entity_id = "select.pool_device_ph_dosing_set"
    before = hass.states.get(entity_id)
    assert before is not None

    client.is_connected = False
    client.set_select = AsyncMock(return_value=False)

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "acid"},
            blocking=True,
        )

    assert excinfo.value.translation_key == "cannot_connect"

    after = hass.states.get(entity_id)
    assert after is not None
    assert before.state == after.state


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_actions_write_rejected_select(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """When the client write method returns False, ServiceValidationError('write_rejected') is raised."""
    client = mock_pooldose_client
    entity_id = "select.pool_device_ph_dosing_set"
    before = hass.states.get(entity_id)
    assert before is not None

    client.set_select = AsyncMock(return_value=False)

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": "acid"},
            blocking=True,
        )

    assert excinfo.value.translation_key == "write_rejected"

    after = hass.states.get(entity_id)
    assert after is not None
    assert before.state == after.state
