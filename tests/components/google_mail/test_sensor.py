"""Sensor tests for the Google Mail integration."""

from datetime import timedelta
from unittest.mock import Mock, patch

from aiohttp.client_exceptions import ClientResponseError
from httplib2 import Response
import pytest

from homeassistant import config_entries
from homeassistant.components.google_mail.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.util import dt as dt_util

from .conftest import SENSOR, TOKEN, ComponentSetup

from tests.common import async_fire_time_changed, async_load_fixture


@pytest.mark.parametrize(
    ("fixture", "result"),
    [
        ("get_vacation", "2022-11-18T05:00:00+00:00"),
        ("get_vacation_no_dates", STATE_UNKNOWN),
        ("get_vacation_off", STATE_UNKNOWN),
    ],
)
async def test_sensors(
    hass: HomeAssistant, setup_integration: ComponentSetup, fixture: str, result: str
) -> None:
    """Test we get sensor data."""
    await setup_integration()

    state = hass.states.get(SENSOR)
    assert state.state == "2022-11-18T05:00:00+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP

    with patch(
        "httplib2.Http.request",
        return_value=(
            Response({}),
            bytes(
                await async_load_fixture(hass, f"{fixture}.json", DOMAIN),
                encoding="UTF-8",
            ),
        ),
    ):
        next_update = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(SENSOR)
    assert state.state == result


async def test_sensor_reauth_trigger(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test reauth is triggered after a refresh error."""
    await setup_integration()

    with patch(
        TOKEN,
        side_effect=OAuth2TokenRequestReauthError(
            request_info=Mock(),
            domain=DOMAIN,
        ),
    ):
        next_update = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH


@pytest.mark.parametrize(
    "side_effect",
    [
        OAuth2TokenRequestTransientError(request_info=Mock(), domain=DOMAIN),
        OAuth2TokenRequestError(request_info=Mock(), domain=DOMAIN),
        ClientResponseError(request_info=Mock(), history=(), status=401),
        ClientResponseError(request_info=Mock(), history=(), status=429),
    ],
    ids=[
        "oauth_transient_error",
        "oauth_generic_error",
        "legacy_client_response_4xx",
        "legacy_rate_limited",
    ],
)
async def test_sensor_token_error_no_reauth(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    side_effect: Exception | type[Exception],
) -> None:
    """Test retryable/runtime token errors do not start reauth."""
    await setup_integration()

    with patch(TOKEN, side_effect=side_effect):
        next_update = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert not hass.config_entries.flow.async_progress()
