"""Define tests for the AEMET OpenData coordinator."""

from unittest.mock import patch

from aemet_opendata.exceptions import AemetError, AuthError
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components import persistent_notification
from homeassistant.components.aemet.const import (
    CONF_API_KEY_DATE,
    CONF_API_KEY_REMINDER,
    DOMAIN,
)
from homeassistant.components.aemet.coordinator import WEATHER_UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .util import async_init_integration

NOTIFICATION_ID = f"{DOMAIN}_api_key_expiry_7442b231f139e813fc1939281123f220"


async def test_coordinator_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test error on coordinator update."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await async_init_integration(hass)

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AemetError,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("weather.aemet")
        assert state.state == STATE_UNAVAILABLE


async def test_coordinator_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test auth error on coordinator update starts a reauth flow."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await async_init_integration(hass)

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AuthError,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_coordinator_auth_error_dismisses_reminder(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test auth error dismisses an active reminder."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-03-30 12:00:00+00:00")
    await async_init_integration(
        hass,
        data={CONF_API_KEY_DATE: "2021-01-01"},
        options={CONF_API_KEY_REMINDER: True},
    )

    assert (
        NOTIFICATION_ID
        in persistent_notification._async_get_or_create_notifications(hass)
    )

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AuthError,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        NOTIFICATION_ID
        not in persistent_notification._async_get_or_create_notifications(hass)
    )


async def test_coordinator_auth_error_cancels_pending_reminder(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test auth error cancels a pending reminder."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    await async_init_integration(
        hass,
        data={CONF_API_KEY_DATE: "2021-01-01"},
        options={CONF_API_KEY_REMINDER: True},
    )

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AuthError,
    ):
        freezer.tick(WEATHER_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    freezer.move_to("2021-03-29 09:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        NOTIFICATION_ID
        not in persistent_notification._async_get_or_create_notifications(hass)
    )
