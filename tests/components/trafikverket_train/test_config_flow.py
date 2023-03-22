"""Test the Trafikverket Train config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.trafikverket_train.const import (
    CONF_FROM,
    CONF_TIME,
    CONF_TO,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_station",
    ), patch(
        "homeassistant.components.trafikverket_train.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: ["mon", "fri"],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Stockholm C to Uppsala C at 10:00"
    assert result2["data"] == {
        "api_key": "1234567890",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Stockholm C",
        "to": "Uppsala C",
        "time": "10:00",
        "weekday": ["mon", "fri"],
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id == "{}-{}-{}-{}".format(
        "stockholmc", "uppsalac", "10:00", "['mon', 'fri']"
    )


async def test_form_entry_already_exist(hass: HomeAssistant) -> None:
    """Test flow aborts when entry already exist."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Stockholm C",
            CONF_TO: "Uppsala C",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
        },
        unique_id=f"stockholmc-uppsalac-10:00-{WEEKDAYS}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_station",
    ), patch(
        "homeassistant.components.trafikverket_train.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "10:00",
                CONF_WEEKDAY: WEEKDAYS,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error_message", "base_error"),
    [
        (
            "Source: Security, message: Invalid authentication",
            "invalid_auth",
        ),
        (
            "Could not find a station with the specified name",
            "invalid_station",
        ),
        (
            "Found multiple stations with the specified name",
            "more_stations",
        ),
        (
            "Unknown",
            "cannot_connect",
        ),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, error_message: str, base_error: str
) -> None:
    """Test config flow errors."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_station",
        side_effect=ValueError(error_message),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
            },
        )

    assert result4["errors"] == {"base": base_error}


async def test_flow_fails_incorrect_time(hass: HomeAssistant) -> None:
    """Test config flow errors due to bad time."""
    result5 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result5["type"] == FlowResultType.FORM
    assert result5["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_station",
    ):
        result6 = await hass.config_entries.flow.async_configure(
            result5["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_FROM: "Stockholm C",
                CONF_TO: "Uppsala C",
                CONF_TIME: "25:25",
            },
        )

    assert result6["errors"] == {"base": "invalid_time"}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Stockholm C",
            CONF_TO: "Uppsala C",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
        },
        unique_id=f"stockholmc-uppsalac-10:00-{WEEKDAYS}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_station",
    ), patch(
        "homeassistant.components.trafikverket_train.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Stockholm C",
        "to": "Uppsala C",
        "time": "10:00",
        "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }


@pytest.mark.parametrize(
    ("sideeffect", "p_error"),
    [
        (
            ValueError("Source: Security, message: Invalid authentication"),
            "invalid_auth",
        ),
        (
            ValueError("Could not find a station with the specified name"),
            "invalid_station",
        ),
        (
            ValueError("Found multiple stations with the specified name"),
            "more_stations",
        ),
        (
            ValueError("Unknown"),
            "cannot_connect",
        ),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant, sideeffect: Exception, p_error: str
) -> None:
    """Test a reauthentication flow with error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_NAME: "Stockholm C to Uppsala C at 10:00",
            CONF_FROM: "Stockholm C",
            CONF_TO: "Uppsala C",
            CONF_TIME: "10:00",
            CONF_WEEKDAY: WEEKDAYS,
        },
        unique_id=f"stockholmc-uppsalac-10:00-{WEEKDAYS}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_station",
        side_effect=sideeffect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567890"},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": p_error}

    with patch(
        "homeassistant.components.trafikverket_train.config_flow.TrafikverketTrain.async_get_train_station",
    ), patch(
        "homeassistant.components.trafikverket_train.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "name": "Stockholm C to Uppsala C at 10:00",
        "from": "Stockholm C",
        "to": "Uppsala C",
        "time": "10:00",
        "weekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    }
