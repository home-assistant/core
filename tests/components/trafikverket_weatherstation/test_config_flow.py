"""Test the Trafikverket weatherstation config flow."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.trafikverket_weatherstation.sensor import SENSOR_TYPES
from homeassistant.const import CONF_API_KEY, CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from tests.common import MockConfigEntry

SENSOR_LIST: list[str | None] = {description.key for (description) in SENSOR_TYPES}

DOMAIN = "trafikverket_weatherstation"
CONF_STATION = "station"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TVWeatherConfigFlow.validate_input",
        return_value="connected",
    ), patch(
        "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Vallby Vasteras",
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Vallby Vasteras"
    assert result2["data"] == {
        "name": "Vallby Vasteras",
        "api_key": "1234567890",
        "station": "Vallby",
        "monitored_conditions": json.dumps(list(SENSOR_LIST)),
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TVWeatherConfigFlow.validate_input",
        return_value="connected",
    ), patch(
        "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: "Vallby Vasteras",
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Vallby Vasteras"
    assert result2["data"] == {
        "name": "Vallby Vasteras",
        "api_key": "1234567890",
        "station": "Vallby",
        "monitored_conditions": json.dumps(list(SENSOR_LIST)),
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "Vallby Vasteras",
            CONF_API_KEY: "1234567890",
            CONF_STATION: "Vallby",
            CONF_MONITORED_CONDITIONS: json.dumps(list(SENSOR_LIST)),
        },
        unique_id="Vallby Vasteras",
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_weatherstation.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TVWeatherConfigFlow.validate_input",
        return_value="connected",
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_NAME: "Vallby Vasteras",
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "abort"
    assert result3["reason"] == "already_configured"


@pytest.mark.parametrize(
    "errormessage,baseerror",
    [
        (
            "Source: Security, message: Invalid authentication",
            "invalid_auth",
        ),
        (
            "Could not find a weather station with the specified name",
            "invalid_station",
        ),
        (
            "Found multiple weather stations with the specified name",
            "more_stations",
        ),
        (
            "Unknown",
            "cannot_connect",
        ),
    ],
)
async def test_flow_fails(hass, errormessage: str, baseerror: str):
    """Test that config flow fails on faulty credentials."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == RESULT_TYPE_FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.trafikverket_weatherstation.config_flow.TVWeatherConfigFlow.validate_input",
        return_value=errormessage,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={
                CONF_NAME: "Vallby Vasteras",
                CONF_API_KEY: "1234567890",
                CONF_STATION: "Vallby",
            },
        )

    assert result4["errors"] == {"base": baseerror}
