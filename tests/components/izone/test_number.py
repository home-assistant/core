"""Tests for iZone number platform."""

from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
from pizone import ControllerCommandError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.izone.const import DOMAIN
from homeassistant.components.izone.coordinator import UPDATE_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from . import setup_integration

DAMPER_MIN_ENTITY = "number.living_room_damper_minimum"
DAMPER_MAX_ENTITY = "number.living_room_damper_maximum"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the number platform for these tests."""
    return [Platform.NUMBER]


@pytest.mark.usefixtures("init_integration")
async def test_number_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Damper limit numbers are created for each zone."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_numbers_linked_to_zone_device(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Damper limit numbers attach to the zone device, not the controller."""
    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "000000001", 0), mock_config_entry.entry_id
    )
    assert zone_device is not None

    for entity_id in (DAMPER_MIN_ENTITY, DAMPER_MAX_ENTITY):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == zone_device.id


@pytest.mark.parametrize(
    ("entity_id", "setter"),
    [
        pytest.param(DAMPER_MIN_ENTITY, "set_airflow_min", id="min"),
        pytest.param(DAMPER_MAX_ENTITY, "set_airflow_max", id="max"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_damper_limit(
    hass: HomeAssistant,
    mock_zones: list[Mock],
    entity_id: str,
    setter: str,
) -> None:
    """Setting a damper limit sends an integer percent to the zone."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 35},
        blocking=True,
    )

    getattr(mock_zones[0], setter).assert_awaited_once_with(35)


@pytest.mark.usefixtures("init_integration")
async def test_set_damper_limit_off_step_rejected(
    hass: HomeAssistant,
    mock_zones: list[Mock],
) -> None:
    """Values that are not a multiple of 5% are rejected before reaching pizone."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: DAMPER_MIN_ENTITY, ATTR_VALUE: 42},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "invalid_airflow_step"
    mock_zones[0].set_airflow_min.assert_not_awaited()


@pytest.mark.parametrize(
    ("command_error", "expect_unavailable", "translation_key"),
    [
        pytest.param(
            ControllerCommandError("rejected"),
            False,
            "command_rejected",
            id="command_error_stays_available",
        ),
        pytest.param(
            ConnectionError("disconnected"),
            True,
            "unable_to_connect",
            id="connection_error_marks_unavailable",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_damper_limit_error_handling(
    hass: HomeAssistant,
    mock_zones: list[Mock],
    command_error: Exception,
    expect_unavailable: bool,
    translation_key: str,
) -> None:
    """Rejected and transport failures raise; only transport clears availability."""
    mock_zones[0].set_airflow_max = AsyncMock(side_effect=command_error)
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: DAMPER_MAX_ENTITY, ATTR_VALUE: 80},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    is_unavailable = hass.states.get(DAMPER_MAX_ENTITY).state == STATE_UNAVAILABLE
    assert is_unavailable is expect_unavailable


@pytest.mark.parametrize(
    ("airflow_lock", "airflow_min_lock", "min_state", "max_state"),
    [
        pytest.param(False, False, "0", "100", id="unlocked"),
        pytest.param(False, True, STATE_UNAVAILABLE, "100", id="min_locked"),
        pytest.param(True, True, STATE_UNAVAILABLE, STATE_UNAVAILABLE, id="locked"),
        pytest.param(None, None, "0", "100", id="not_reported"),
    ],
)
@pytest.mark.usefixtures("mock_create_discovery")
async def test_airflow_lock_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
    airflow_lock: bool | None,
    airflow_min_lock: bool | None,
    min_state: str,
    max_state: str,
) -> None:
    """The installer airflow locks make the matching damper limits unavailable."""
    mock_controller.airflow_lock = airflow_lock
    mock_controller.airflow_min_lock = airflow_min_lock

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(DAMPER_MIN_ENTITY).state == min_state
    assert hass.states.get(DAMPER_MAX_ENTITY).state == max_state


@pytest.mark.usefixtures("init_integration")
async def test_airflow_lock_follows_refresh(
    hass: HomeAssistant,
    mock_controller: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Locking the airflow on the controller is picked up on the next refresh."""
    assert hass.states.get(DAMPER_MAX_ENTITY).state == "100"

    mock_controller.airflow_lock = True
    mock_controller.airflow_min_lock = True
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(DAMPER_MIN_ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get(DAMPER_MAX_ENTITY).state == STATE_UNAVAILABLE
