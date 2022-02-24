"""Test the Sensibo config flow."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import aiohttp
from pysensibo import AuthenticationError, SensiboError
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry

DOMAIN = "sensibo"


def devices():
    """Return list of test devices."""
    return (yield from [{"id": "xyzxyz"}, {"id": "abcabc"}])


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value=devices(),
    ), patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        "api_key": "1234567890",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value=devices(),
    ), patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Sensibo"
    assert result2["data"] == {
        "api_key": "1234567890",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
        },
        unique_id="1234567890",
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value=devices(),
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_configured"


@pytest.mark.parametrize(
    "error_message",
    [
        (aiohttp.ClientConnectionError),
        (asyncio.TimeoutError),
        (AuthenticationError),
        (SensiboError),
    ],
)
async def test_flow_fails(hass: HomeAssistant, error_message) -> None:
    """Test config flow errors."""

    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == RESULT_TYPE_FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        side_effect=error_message,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )

    assert result4["errors"] == {"base": "cannot_connect"}
