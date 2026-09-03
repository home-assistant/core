"""Tests for Poolside variable-speed controls exposed as fan entities."""

from aiopoolside import PoolsideControl
from aiopoolside.const import ControlType
import pytest

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakePoolsideClient, make_control

PUMP_UUID = "pump-1"
ENTITY_ID = "fan.pool_pool_pump"
JETS_UUID = "spa-jets-1"
POOL_DEVICE_UUID = "item-pump-1"
ITEM_ENTITY_ID = "fan.pool_spa_jets"


@pytest.fixture
def controls() -> list[PoolsideControl]:
    """A WATER_FEATURE control with four discrete speed steps.

    A second control has a distinct ControlItemUUID from its own UUID, to
    cover status pushes keyed by ControlItemUUID (the underlying PoolDevice)
    rather than the control's own UUID.
    """
    return [
        make_control(
            PUMP_UUID,
            "Pool Pump",
            ControlType.WATER_FEATURE,
            SpeedIncrements=[25, 50, 75, 100],
        ),
        make_control(
            JETS_UUID,
            "Spa Jets",
            ControlType.WATER_FEATURE,
            SpeedIncrements=[25, 50, 75, 100],
            ControlItemUUID=POOL_DEVICE_UUID,
        ),
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_water_feature_uses_fountain_icon_translation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """WATER_FEATURE fans carry the water_feature icon translation key.

    The icon itself (mdi:fountain in icons.json) is resolved by the
    frontend from this key; the name still comes from the control.
    """
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.translation_key == "water_feature"

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["friendly_name"] == "Pool Pool Pump"


@pytest.mark.usefixtures("setup_integration")
async def test_state_reflects_status(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """The fan's state and percentage track Status/NormalizedPowerLevel pushes."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(PUMP_UUID, "Status", "ON")
    fake_client.set_status(PUMP_UUID, "PowerLevel", 50)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50


@pytest.mark.usefixtures("setup_integration")
async def test_ignores_status_pushed_under_control_item_uuid(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Status pushed under ControlItemUUID (the underlying PoolDevice) is ignored.

    ControlItemUUID identifies separate physical hardware, not the control -
    even though its status can look plausible, it must never drive state.
    """
    fake_client.set_status(POOL_DEVICE_UUID, "ActualPowerState", "ON")
    fake_client.set_status(POOL_DEVICE_UUID, "PowerState", "ON")
    await hass.async_block_till_done()

    state = hass.states.get(ITEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("setup_integration")
async def test_state_reflects_push_keyed_by_own_uuid(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """The control's own UUID drives state, regardless of its ControlItemUUID."""
    fake_client.set_status(JETS_UUID, "ActualPowerState", "ON")
    await hass.async_block_till_done()

    state = hass.states.get(ITEM_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_set_percentage_snaps_to_nearest_increment(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Requesting an unsupported percentage snaps to the nearest speed step."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 60},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(
        PUMP_UUID, Status="ON", PowerLevel="50"
    )


@pytest.mark.usefixtures("setup_integration")
async def test_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Setting percentage to 0 turns the control off instead of sending PowerLevel."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(PUMP_UUID, Status="OFF")


@pytest.mark.usefixtures("setup_integration")
async def test_turn_on_without_percentage(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Turning on with no percentage just flips Status, keeping the last speed."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(PUMP_UUID, Status="ON")


@pytest.mark.usefixtures("setup_integration")
async def test_turn_off(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Turning off sends Status=OFF."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(PUMP_UUID, Status="OFF")
