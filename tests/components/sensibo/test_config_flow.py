"""Test the Sensibo config flow."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import aiohttp
from pysensibo.exceptions import AuthenticationError, SensiboError
import pytest

from homeassistant import config_entries
from homeassistant.components.sensibo.config_flow import (
    CANNOT_CONNECT,
    INVALID_AUTH,
    NO_DEVICES,
    NO_USERNAME,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry

DOMAIN = "sensibo"


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
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
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
    assert result2["version"] == 2
    assert result2["data"] == {
        "api_key": "1234567890",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
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
        unique_id="username",
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
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
    "error_message, p_error",
    [
        (aiohttp.ClientConnectionError, CANNOT_CONNECT),
        (asyncio.TimeoutError, CANNOT_CONNECT),
        (AuthenticationError, INVALID_AUTH),
        (SensiboError, CANNOT_CONNECT),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, error_message: Exception, p_error: str
) -> None:
    """Test config flow errors."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        side_effect=error_message,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )

    assert result2["errors"] == {"base": p_error}

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ), patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567891",
            },
        )

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Sensibo"
    assert result3["data"] == {
        "api_key": "1234567891",
    }


async def test_flow_get_no_devices(hass: HomeAssistant) -> None:
    """Test config flow get no devices from api."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value={"result": []},
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_me",
        return_value={"result": {}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )

    assert result2["errors"] == {"base": NO_DEVICES}


async def test_flow_get_no_username(hass: HomeAssistant) -> None:
    """Test config flow get no username from api."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.config_flow.SensiboClient.async_get_me",
        return_value={"result": {}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )

    assert result2["errors"] == {"base": NO_USERNAME}
