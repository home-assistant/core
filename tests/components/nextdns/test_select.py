"""Test select of NextDNS integration."""
import asyncio
from datetime import timedelta
from unittest.mock import Mock, patch

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError
import pytest

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import SETTINGS, init_integration

from tests.common import async_fire_time_changed


async def test_select(hass: HomeAssistant) -> None:
    """Test states of the select entities."""
    registry = er.async_get(hass)

    await init_integration(hass)

    state = hass.states.get("select.fake_profile_logs_location")
    assert state
    assert state.state == "switzerland"
    assert state.attributes.get("options") == [
        "switzerland",
        "european_union",
        "great_britain",
        "united_states",
    ]
    assert state.attributes.get("icon") == "mdi:archive-marker-outline"

    entry = registry.async_get("select.fake_profile_logs_location")
    assert entry
    assert entry.unique_id == "xyz12_logs_location"

    state = hass.states.get("select.fake_profile_logs_retention")
    assert state
    assert state.state == "one_month"
    assert state.attributes.get("options") == [
        "one_hour",
        "six_hours",
        "one_day",
        "one_week",
        "one_month",
        "three_months",
        "six_months",
        "one_year",
        "two_years",
    ]
    assert state.attributes.get("icon") == "mdi:history"

    entry = registry.async_get("select.fake_profile_logs_retention")
    assert entry
    assert entry.unique_id == "xyz12_logs_retention"


@pytest.mark.parametrize(
    "entity,from_option,to_option",
    [
        ("select.fake_profile_logs_location", "switzerland", "european_union"),
        ("select.fake_profile_logs_retention", "one_month", "one_year"),
    ],
)
async def test_select_option(
    hass: HomeAssistant, entity: str, from_option: str, to_option: str
) -> None:
    """Test the option can be selected."""
    await init_integration(hass)

    state = hass.states.get(entity)
    assert state
    assert state.state == from_option

    with patch(
        "homeassistant.components.nextdns.NextDns._http_request",
        return_value={"success": True},
    ) as mock_select_option:
        assert await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity, ATTR_OPTION: to_option},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity)
        assert state
        assert state.state == to_option

        mock_select_option.assert_called_once()


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("select.fake_profile_logs_retention")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "one_month"

    future = utcnow() + timedelta(minutes=10)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        side_effect=ApiError("API Error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("select.fake_profile_logs_retention")
    assert state
    assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=20)
    with patch(
        "homeassistant.components.nextdns.NextDns.get_settings",
        return_value=SETTINGS,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("select.fake_profile_logs_retention")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "one_month"


@pytest.mark.parametrize(
    "exc",
    [
        ApiError(Mock()),
        asyncio.TimeoutError,
        ClientConnectorError(Mock(), Mock()),
        ClientError,
    ],
)
async def test_select_option_failure(hass: HomeAssistant, exc: Exception) -> None:
    """Tests that the select option service throws HomeAssistantError."""
    await init_integration(hass)

    with patch(
        "homeassistant.components.nextdns.NextDns._http_request", side_effect=exc
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: "select.fake_profile_logs_location",
                    ATTR_OPTION: "european_union",
                },
                blocking=True,
            )


async def test_select_invalid_option(hass: HomeAssistant) -> None:
    """Tests that the select option service throws ValueError."""
    await init_integration(hass)

    with pytest.raises(ValueError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.fake_profile_logs_location",
                ATTR_OPTION: "wrong_location",
            },
            blocking=True,
        )
