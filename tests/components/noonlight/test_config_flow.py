"""Config-flow tests for the Noonlight integration."""

from __future__ import annotations

from unittest.mock import patch

from httpx import Response
from noonlight_dispatch import NoonlightError
import respx

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.noonlight.const import (
    ALL_NOONLIGHT_SERVICES,
    CONF_ADDRESS,
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_CITY,
    CONF_DEDUPE_SECONDS,
    CONF_DEFAULT_ENTRY_DELAY,
    CONF_ENVIRONMENT,
    CONF_NAME,
    CONF_PHONE,
    CONF_SAFETY_ACK,
    CONF_SERVICES_GRANTED,
    CONF_STATE,
    CONF_ZIP,
    DOMAIN,
    ENV_CUSTOM,
    ENV_PRODUCTION,
    ENV_SANDBOX,
)
from homeassistant.core import HomeAssistant

_CALLER = {
    CONF_NAME: "Main",
    CONF_PHONE: "+15555550123",
    CONF_ADDRESS: "1 Test St",
    CONF_CITY: "Testville",
    CONF_STATE: "CA",
    CONF_ZIP: "90001",
}
_DEFAULTS = {
    CONF_DEFAULT_ENTRY_DELAY: 30,
    CONF_DEDUPE_SECONDS: 300,
    CONF_SERVICES_GRANTED: ALL_NOONLIGHT_SERVICES,
}


def _mock_token_probe(status: int = 404) -> None:
    """A GET against the bogus connection-test id validates the token."""
    respx.route(method="GET", url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
        return_value=Response(status)
    )


@respx.mock
async def test_sandbox_flow_skips_safety(hass: HomeAssistant) -> None:
    """Sandbox setup completes without the production safety step."""
    _mock_token_probe()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    assert result["step_id"] == "caller"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], _CALLER)
    assert result["step_id"] == "defaults"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULTS
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Main"
    assert result["data"][CONF_ENVIRONMENT] == ENV_SANDBOX
    assert result["options"][CONF_SERVICES_GRANTED] == ALL_NOONLIGHT_SERVICES


@respx.mock
async def test_production_requires_safety_ack(hass: HomeAssistant) -> None:
    """Production setup must pass the safety step before creating the entry."""
    _mock_token_probe()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_PRODUCTION},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _CALLER)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULTS
    )
    assert result["step_id"] == "safety"

    # Refusing the ack keeps us on the safety step with an error.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SAFETY_ACK: False}
    )
    assert result["step_id"] == "safety"
    assert result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SAFETY_ACK: True}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SAFETY_ACK] is True


@respx.mock
async def test_invalid_auth_surfaced(hass: HomeAssistant) -> None:
    """A 401 during validation shows an invalid_auth error."""
    respx.route(method="GET", url__regex=r".*/status").mock(return_value=Response(401))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "bad", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"


@respx.mock
async def test_cannot_connect_surfaced(hass: HomeAssistant) -> None:
    """A transport failure during validation shows a cannot_connect error."""
    respx.route(method="GET", url__regex=r".*/status").mock(
        side_effect=__import__("httpx").ConnectError("down")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


@respx.mock
async def test_server_error_surfaces_cannot_connect(hass: HomeAssistant) -> None:
    """A 5xx during validation must not be accepted as a valid token."""
    respx.route(method="GET", url__regex=r".*/status").mock(return_value=Response(503))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_unexpected_library_error_is_reachable(hass: HomeAssistant) -> None:
    """A bare NoonlightError during validation is treated as reachable."""
    with patch(
        "homeassistant.components.noonlight.config_flow.NoonlightClient."
        "get_alarm_status",
        side_effect=NoonlightError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
        )
    assert result["step_id"] == "caller"


async def test_custom_requires_base_url(hass: HomeAssistant) -> None:
    """Selecting the custom environment without a URL is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_CUSTOM},
    )
    assert result["step_id"] == "user"
    assert result["errors"][CONF_BASE_URL] == "base_url_required"


@respx.mock
async def test_duplicate_address_aborts(hass: HomeAssistant, setup_entry) -> None:
    """Adding a second entry for the same environment+address+ZIP is rejected.

    ``setup_entry`` already configures the sandbox entry at '1 Test St' /
    '90001'; re-adding the same property must abort as already_configured.
    """
    _mock_token_probe()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _CALLER)

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@respx.mock
async def test_different_address_allowed(hass: HomeAssistant, setup_entry) -> None:
    """A different street address is a distinct property and is allowed.

    Even when reusing the same environment + token, a distinct address is a
    distinct property.
    """
    _mock_token_probe()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**_CALLER, CONF_ADDRESS: "2 Other Ave"}
    )
    # Distinct address -> not aborted; advances to the defaults step.
    assert result["step_id"] == "defaults"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _DEFAULTS
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


@respx.mock
async def test_options_flow(hass: HomeAssistant, setup_entry) -> None:
    """Options flow updates entry delay, dedupe, and granted services."""
    respx.get(url__regex=r".*/status").mock(return_value=Response(404))
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_DEFAULT_ENTRY_DELAY: 10,
            CONF_DEDUPE_SECONDS: 60,
            CONF_SERVICES_GRANTED: ["police"],
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert setup_entry.options[CONF_DEFAULT_ENTRY_DELAY] == 10
    assert setup_entry.options[CONF_SERVICES_GRANTED] == ["police"]
