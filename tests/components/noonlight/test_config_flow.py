"""Config-flow tests for the Noonlight integration."""

import httpx
from httpx import Response
import respx

from homeassistant import config_entries
from homeassistant.components.noonlight.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import STATUS_RE

from tests.common import MockConfigEntry


@respx.mock
async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A valid token creates the entry."""
    respx.get(url__regex=STATUS_RE).mock(return_value=Response(404))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "tok"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Noonlight"
    assert result["data"][CONF_API_TOKEN] == "tok"


@respx.mock
async def test_invalid_auth(hass: HomeAssistant) -> None:
    """A 401 during validation shows an invalid_auth error."""
    respx.get(url__regex=STATUS_RE).mock(return_value=Response(401))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "bad"}
    )

    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"


@respx.mock
async def test_cannot_connect(hass: HomeAssistant) -> None:
    """A transport failure during validation shows a cannot_connect error."""
    respx.get(url__regex=STATUS_RE).mock(side_effect=httpx.ConnectError("down"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "tok"}
    )

    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


@respx.mock
async def test_server_error_is_cannot_connect(hass: HomeAssistant) -> None:
    """A 5xx during validation must not be accepted as a valid token."""
    respx.get(url__regex=STATUS_RE).mock(return_value=Response(503))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "tok"}
    )

    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_single_instance_allowed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Only one Noonlight entry is allowed."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
