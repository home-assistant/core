"""Test the Sensibo config flow."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import aiohttp
from pysensibo.exceptions import AuthenticationError, SensiboError
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DOMAIN = "sensibo"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
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

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["version"] == 2
    assert result2["data"] == {
        "api_key": "1234567890",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_message", "p_error"),
    [
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (AuthenticationError, "invalid_auth"),
        (SensiboError, "cannot_connect"),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, error_message: Exception, p_error: str
) -> None:
    """Test config flow errors."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
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
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
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

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Sensibo"
    assert result3["data"] == {
        "api_key": "1234567891",
    }


async def test_flow_get_no_devices(hass: HomeAssistant) -> None:
    """Test config flow get no devices from api."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": []},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )

    assert result2["errors"] == {"base": "no_devices"}


async def test_flow_get_no_username(hass: HomeAssistant) -> None:
    """Test config flow get no username from api."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )

    assert result2["errors"] == {"base": "no_username"}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        unique_id="username",
        data={"api_key": "1234567890"},
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
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ) as mock_sensibo, patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {"api_key": "1234567891"}

    assert len(mock_sensibo.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("sideeffect", "p_error"),
    [
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (AuthenticationError, "invalid_auth"),
        (SensiboError, "cannot_connect"),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant, sideeffect: Exception, p_error: str
) -> None:
    """Test a reauthentication flow with error."""
    entry = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        unique_id="username",
        data={"api_key": "1234567890"},
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
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
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
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value={"result": {"username": "username"}},
    ), patch(
        "homeassistant.components.sensibo.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {"api_key": "1234567891"}


@pytest.mark.parametrize(
    ("get_devices", "get_me", "p_error"),
    [
        (
            {"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
            {"result": {}},
            "no_username",
        ),
        (
            {"result": []},
            {"result": {"username": "username"}},
            "no_devices",
        ),
        (
            {"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
            {"result": {"username": "username2"}},
            "incorrect_api_key",
        ),
    ],
)
async def test_flow_reauth_no_username_or_device(
    hass: HomeAssistant,
    get_devices: dict[str, Any],
    get_me: dict[str, Any],
    p_error: str,
) -> None:
    """Test config flow get no username from api."""
    entry = MockConfigEntry(
        version=2,
        domain=DOMAIN,
        unique_id="username",
        data={"api_key": "1234567890"},
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
        return_value=get_devices,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
        return_value=get_me,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": p_error}
