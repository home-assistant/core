"""Tests for the Philips TV ambilight light."""

from collections.abc import Generator
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from haphilipsjs import GeneralFailure, PhilipsTV
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.philips_js.const import UNREACHABLE_GRACE, WAKE_TIMEOUT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

LIGHT_ENTITY_ID = "light.philips_tv_ambilight"
COORDINATOR = "homeassistant.components.philips_js.coordinator"
LIGHT = "homeassistant.components.philips_js.light"


class FakeClock:
    """Monotonic clock that only advances when told to."""

    def __init__(self) -> None:
        """Initialize the clock."""
        self.now = 1000.0

    def monotonic(self) -> float:
        """Return the current time."""
        return self.now

    async def sleep(self, delay: float) -> None:
        """Advance the clock instead of sleeping."""
        self.now += delay


@pytest.fixture
def clock() -> Generator[FakeClock]:
    """Replace the time and sleep used by the integration with a fake clock."""
    fake = FakeClock()
    fake_asyncio = MagicMock(sleep=fake.sleep)
    with (
        patch(f"{COORDINATOR}.time", SimpleNamespace(monotonic=fake.monotonic)),
        patch(f"{COORDINATOR}.asyncio", fake_asyncio),
        patch(f"{LIGHT}.asyncio", fake_asyncio),
    ):
        yield fake


@pytest.fixture
async def setup_light(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    clock: FakeClock,
) -> None:
    """Set up the integration with a TV that has an idle ambilight."""
    mock_tv.json_feature_supported.return_value = True
    mock_tv.powerstate = "On"
    mock_tv.screenstate = "On"
    mock_tv.huelamp_power = "Off"
    mock_tv.ambilight_mode = "internal"
    mock_tv.ambilight_modes = ["internal", "manual", "expert", "lounge"]
    mock_tv.update.return_value = True
    mock_tv.setAmbilightMode.return_value = True
    mock_tv.setAmbilightCurrentConfiguration.return_value = True
    mock_tv.setAmbilightCached.return_value = True

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def _fail_updates(mock_tv: PhilipsTV) -> None:
    """Make the TV drop all requests, like api.update() does in standby."""

    async def update() -> bool:
        mock_tv.on = False
        return False

    mock_tv.update.side_effect = update


async def _poll(hass: HomeAssistant, clock: FakeClock, seconds: float) -> None:
    """Advance time and run a coordinator poll."""
    clock.now += seconds
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_light")
async def test_transient_failure_keeps_state(
    hass: HomeAssistant, mock_tv: PhilipsTV, clock: FakeClock
) -> None:
    """Test a failed poll within the grace period keeps the light available."""
    assert (state := hass.states.get(LIGHT_ENTITY_ID))
    assert state.state == STATE_ON

    _fail_updates(mock_tv)
    await _poll(hass, clock, 30)

    assert mock_tv.on is True
    assert (state := hass.states.get(LIGHT_ENTITY_ID))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_light")
async def test_general_failure_keeps_state(
    hass: HomeAssistant, mock_tv: PhilipsTV, clock: FakeClock
) -> None:
    """Test an exception from the API within grace does not fail the update."""
    mock_tv.update.side_effect = GeneralFailure("dropped")
    await _poll(hass, clock, 30)

    assert (state := hass.states.get(LIGHT_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_light")
async def test_failure_after_grace_is_off_but_available(
    hass: HomeAssistant, mock_tv: PhilipsTV, clock: FakeClock
) -> None:
    """Test a TV that stays silent past the grace period is off, not unavailable."""
    mock_tv.ambilight_current_configuration = {
        "styleName": "FOLLOW_VIDEO",
        "isExpert": False,
        "menuSetting": "STANDARD",
    }
    mock_tv.ambilight_styles = {"FOLLOW_VIDEO": {"menuSettings": ["STANDARD"]}}
    await _poll(hass, clock, 30)
    assert (state := hass.states.get(LIGHT_ENTITY_ID))
    assert state.state == STATE_ON

    _fail_updates(mock_tv)
    await _poll(hass, clock, UNREACHABLE_GRACE + 1)

    assert mock_tv.on is False
    assert (state := hass.states.get(LIGHT_ENTITY_ID))
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_light")
async def test_turn_on_retries(
    hass: HomeAssistant, mock_tv: PhilipsTV, clock: FakeClock
) -> None:
    """Test turn_on retries a dropped command and then succeeds."""
    mock_tv.setAmbilightCached.side_effect = [
        GeneralFailure("dropped"),
        GeneralFailure("dropped"),
        True,
    ]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
        blocking=True,
    )

    assert mock_tv.setAmbilightCached.call_count == 3


@pytest.mark.usefixtures("setup_light")
async def test_turn_on_gives_up_after_three_attempts(
    hass: HomeAssistant, mock_tv: PhilipsTV
) -> None:
    """Test turn_on raises once all attempts failed."""
    mock_tv.setAmbilightCached.side_effect = GeneralFailure("dropped")

    with pytest.raises(GeneralFailure):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
            blocking=True,
        )

    assert mock_tv.setAmbilightCached.call_count == 3


@pytest.mark.usefixtures("setup_light")
async def test_turn_on_waits_for_tv(
    hass: HomeAssistant, mock_tv: PhilipsTV, clock: FakeClock
) -> None:
    """Test turn_on waits for a TV that answers after a few seconds."""
    _fail_updates(mock_tv)
    await _poll(hass, clock, UNREACHABLE_GRACE + 1)
    assert mock_tv.on is False

    answers = iter([False, False, True])

    async def update() -> bool:
        mock_tv.on = next(answers)
        return mock_tv.on

    mock_tv.update.side_effect = update

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
        blocking=True,
    )

    assert mock_tv.setAmbilightCached.called


@pytest.mark.usefixtures("setup_light")
async def test_turn_on_times_out(
    hass: HomeAssistant, mock_tv: PhilipsTV, clock: FakeClock
) -> None:
    """Test turn_on raises after WAKE_TIMEOUT when the TV never answers."""
    _fail_updates(mock_tv)
    await _poll(hass, clock, UNREACHABLE_GRACE + 1)
    start = clock.now

    with pytest.raises(HomeAssistantError, match="TV is not available"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
            blocking=True,
        )

    assert clock.now - start >= WAKE_TIMEOUT
    mock_tv.setAmbilightCached.assert_not_called()


@pytest.mark.usefixtures("setup_light")
async def test_turn_off_unreachable_is_noop(
    hass: HomeAssistant, mock_tv: PhilipsTV, clock: FakeClock
) -> None:
    """Test turn_off on an unreachable TV does nothing and does not raise."""
    _fail_updates(mock_tv)
    await _poll(hass, clock, UNREACHABLE_GRACE + 1)
    assert mock_tv.on is False

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
        blocking=True,
    )

    mock_tv.setAmbilightMode.assert_not_called()
    mock_tv.setAmbilightCurrentConfiguration.assert_not_called()
