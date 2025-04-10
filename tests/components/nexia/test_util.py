"""The sensor tests for the nexia platform."""

from datetime import timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock

from homeassistant.components.nexia import util
from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from tests.common import async_fire_time_changed


async def test_is_invalid_auth_code() -> None:
    """Test for invalid auth."""

    assert util.is_invalid_auth_code(HTTPStatus.UNAUTHORIZED) is True
    assert util.is_invalid_auth_code(HTTPStatus.FORBIDDEN) is True
    assert util.is_invalid_auth_code(HTTPStatus.NOT_FOUND) is False


async def test_percent_conv() -> None:
    """Test percentage conversion."""

    assert util.percent_conv(0.12) == 12.0
    assert util.percent_conv(0.123) == 12.3


async def test_resettable_single_shot(hass: HomeAssistant) -> None:
    """Test class SingleShot."""
    calls = []
    single_shot = util.SingleShot(
        hass, timedelta(seconds=0.01), AsyncMock(side_effect=lambda: calls.append(None))
    )

    # Fire once.
    single_shot.reset_delayed_action_trigger()
    assert len(calls) == 0
    assert single_shot._cancel_delayed_action is not None

    # Fire again while pending.
    single_shot.reset_delayed_action_trigger()
    assert len(calls) == 0
    assert single_shot._cancel_delayed_action is not None

    # Wait for time to run.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert single_shot._cancel_delayed_action is None

    # Fire again, then exercise shutdown path.
    single_shot.reset_delayed_action_trigger()
    assert len(calls) == 1
    assert single_shot._cancel_delayed_action is not None
    single_shot.async_shutdown()
    assert len(calls) == 1
    assert single_shot._cancel_delayed_action is None
