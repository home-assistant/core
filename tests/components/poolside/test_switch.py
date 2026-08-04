"""Tests for Poolside BLOWER controls exposed as switch entities."""

from aiopoolside import PoolsideControl
from aiopoolside.const import ControlType
import pytest

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakePoolsideClient, make_control

BLOWER_UUID = "blower-1"
ENTITY_ID = "switch.pool_spa_blower"
UNKNOWN_UUID = "unknown-1"
UNKNOWN_ENTITY_ID = "switch.pool_fire_feature"
WATERFALL_UUID = "waterfall-1"
WATERFALL_ENTITY_ID = "switch.pool_waterfall"


@pytest.fixture
def controls() -> list[PoolsideControl]:
    """A BLOWER, an UNKNOWN-typed control, and a single-speed WATER_FEATURE."""
    return [
        make_control(BLOWER_UUID, "Spa Blower", ControlType.BLOWER),
        make_control(UNKNOWN_UUID, "Fire Feature", ControlType.UNKNOWN),
        make_control(
            WATERFALL_UUID,
            "Waterfall",
            ControlType.WATER_FEATURE,
            SpeedIncrements=[100],
        ),
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_unknown_control_type_is_a_switch(hass: HomeAssistant) -> None:
    """A control type this integration doesn't classify is still a plain switch."""
    assert hass.states.get(UNKNOWN_ENTITY_ID) is not None


@pytest.mark.usefixtures("setup_integration")
async def test_water_feature_uses_fountain_icon_translation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """On/off WATER_FEATUREs carry the water_feature icon translation key.

    The icon itself (mdi:fountain in icons.json) is resolved by the
    frontend from this key; other switch types carry no key.
    """
    entry = entity_registry.async_get(WATERFALL_ENTITY_ID)
    assert entry is not None
    assert entry.translation_key == "water_feature"

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.translation_key is None


@pytest.mark.usefixtures("setup_integration")
async def test_state_falls_back_to_our_own_write_echo(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Before any real push arrives, state falls back to our own Status echo."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    fake_client.set_status(BLOWER_UUID, "Status", "ON")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_state_reflects_real_power_state_push(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """A real PowerState push (as actually observed on the wire) updates state."""
    fake_client.set_status(BLOWER_UUID, "PowerState", "ON")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_actual_power_state_wins_over_power_state_and_echo(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """ActualPowerState (ground truth) overrides a stale PowerState/our own echo."""
    fake_client.set_status(BLOWER_UUID, "Status", "ON")
    fake_client.set_status(BLOWER_UUID, "PowerState", "ON")
    fake_client.set_status(BLOWER_UUID, "ActualPowerState", "OFF")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_integration")
async def test_unknown_actual_power_state_falls_through_to_power_state(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Some hardware reports ActualPowerState="UNKNOWN" forever (no relay feedback).

    That's a "no data" sentinel, not ground truth - state must still track
    PowerState instead of getting stuck showing off/unknown.
    """
    fake_client.set_status(BLOWER_UUID, "ActualPowerState", "UNKNOWN")
    fake_client.set_status(BLOWER_UUID, "PowerState", "ON")
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_turn_on(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Turning on sends Status=ON."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(BLOWER_UUID, Status="ON")


@pytest.mark.usefixtures("setup_integration")
async def test_turn_off(
    hass: HomeAssistant,
    fake_client: FakePoolsideClient,
) -> None:
    """Turning off sends Status=OFF."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    fake_client.async_set_desired_state.assert_awaited_with(BLOWER_UUID, Status="OFF")
