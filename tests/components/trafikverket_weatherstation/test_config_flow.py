"""Test the Trafikverket weatherstation config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytrafikverket.exceptions import (
    InvalidAuthentication,
    MultipleWeatherStationsFound,
    NoWeatherStationFound,
)

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DOMAIN = "trafikverket_weatherstation"
CONF_STATION = "station"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
        ),
        patch(
            "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Vallby"
    assert result2["data"] == {
        "api_key": "1234567890",
        "station": "Vallby",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "base_error"),
    [
        (
            InvalidAuthentication,
            "invalid_auth",
        ),
        (
            NoWeatherStationFound,
            "invalid_station",
        ),
        (
            MultipleWeatherStationsFound,
            "more_stations",
        ),
        (
            Exception,
            "cannot_connect",
        ),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, side_effect: Exception, base_error: str
) -> None:
    """Test config flow errors."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
        side_effect=side_effect(),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )

    assert result4["errors"] == {"base": base_error}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_STATION: "Vallby",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
        ),
        patch(
            "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {"api_key": "1234567891", "station": "Vallby"}


@pytest.mark.parametrize(
    ("side_effect", "base_error"),
    [
        (
            InvalidAuthentication,
            "invalid_auth",
        ),
        (
            NoWeatherStationFound,
            "invalid_station",
        ),
        (
            MultipleWeatherStationsFound,
            "more_stations",
        ),
        (
            Exception,
            "cannot_connect",
        ),
    ],
)
async def test_reauth_flow_fails(
    hass: HomeAssistant, side_effect: Exception, base_error: str
) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_STATION: "Vallby",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TrafikverketWeather.async_get_weather",
        side_effect=side_effect(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}
