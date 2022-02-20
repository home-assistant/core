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
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Sensibo"
    assert result["data"] == {
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
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "sideeffect,p_error",
    [
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (asyncio.TimeoutError, "cannot_connect"),
        (AuthenticationError, "invalid_auth"),
        (SensiboError, "cannot_connect"),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, sideeffect: Exception, p_error: str
) -> None:
    """Test config flow errors."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        side_effect=sideeffect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": p_error}

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value=devices(),
    ), patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567891",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Sensibo"
    assert result3["data"] == {"api_key": "1234567891"}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234567890",
        data={"api_key": "1234567890"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        side_effect=AuthenticationError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": entry.unique_id,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
    assert result["step_id"] == "reauth"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value=devices(),
    ) as mock_sensibo, patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {"api_key": "1234567891"}

    assert len(mock_sensibo.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
