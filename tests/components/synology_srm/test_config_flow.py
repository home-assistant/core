"""Tests for the Synology SRM config flow."""

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
import synology_srm
import voluptuous as vol

from homeassistant.components.synology_srm.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_synology_client")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """User-initiated flow creates an entry on success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Synology SRM ({MOCK_CONFIG[CONF_HOST]})"
    assert result["data"] == MOCK_CONFIG


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            requests.exceptions.SSLError("ssl"),
            "ssl_error",
            id="ssl_error",
        ),
        pytest.param(
            requests.exceptions.HTTPError("http"),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            synology_srm.http.SynologyApiError(102, "bad auth"),
            "invalid_auth",
            id="api_error_maps_to_invalid_auth",
        ),
        pytest.param(
            synology_srm.http.SynologyHttpException(401, "unauthorized"),
            "invalid_auth",
            id="http_exception_maps_to_invalid_auth",
        ),
        pytest.param(ValueError("boom"), "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Each validation failure surfaces the right error key, and the form lets us retry."""
    mock_synology_client.mesh.get_system_info.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recovery path: clearing the side effect and submitting again creates the entry.
    mock_synology_client.mesh.get_system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_synology_client")
async def test_user_flow_duplicate_host_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Same host as an existing entry aborts with already_configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_skips_disable_https_verify_when_verify_true(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
) -> None:
    """disable_https_verify is only called when CONF_VERIFY_SSL is False."""
    config: dict[str, Any] = {**MOCK_CONFIG, CONF_VERIFY_SSL: True}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], config)
    await hass.async_block_till_done()

    mock_synology_client.http.disable_https_verify.assert_not_called()


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth confirm updates the entry's password and reloads it."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "newpw"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "newpw"


async def test_reauth_flow_error_then_recovery(
    hass: HomeAssistant,
    mock_synology_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed reauth shows the form again; a subsequent success aborts with reauth_successful."""
    mock_config_entry.add_to_hass(hass)
    mock_synology_client.mesh.get_system_info.side_effect = (
        synology_srm.http.SynologyApiError(102, "bad auth")
    )

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_synology_client.mesh.get_system_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "right"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_synology_client")
async def test_user_flow_form_defaults(hass: HomeAssistant) -> None:
    """The user step renders with the documented defaults for the optional fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    schema = result["data_schema"].schema
    defaults = {
        str(key): key.default() for key in schema if key.default is not vol.UNDEFINED
    }
    assert defaults[CONF_USERNAME] == "admin"
    assert defaults[CONF_PORT] == 8001
    assert defaults[CONF_SSL] is True
