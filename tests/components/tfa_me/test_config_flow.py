"""Test the TFA.me integration: test of config_flow.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from __future__ import annotations

from collections.abc import Mapping
import contextlib
from unittest.mock import patch

import pytest
from tfa_me_ha_local.client import (
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tfa_me.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

type PatchKwargs = Mapping[str, object] | None
type UserInput = dict[str, object]


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the flow starts with the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    (
        "patch_target",
        "patch_kwargs",
        "initial_user_input",
        "error_key",
        "expected_error",
    ),
    [
        (
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID",
            {"side_effect": TFAmeTimeoutError("timeout_connect")},
            {CONF_IP_ADDRESS: "192.168.0.10"},
            "base",
            "timeout_connect",
        ),
        (
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID",
            {"side_effect": TFAmeConnectionError("cannot_connect")},
            {CONF_IP_ADDRESS: "192.168.0.10"},
            "base",
            "cannot_connect",
        ),
        (
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID",
            {"side_effect": TFAmeHTTPError("invalid_response")},
            {CONF_IP_ADDRESS: "192.168.0.10"},
            "base",
            "invalid_response",
        ),
        (
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID",
            {"side_effect": TFAmeJSONError("invalid_response")},
            {CONF_IP_ADDRESS: "192.168.0.10"},
            "base",
            "invalid_response",
        ),
        (
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID",
            {"side_effect": TFAmeException("unknown")},
            {CONF_IP_ADDRESS: "192.168.0.10"},
            "base",
            "unknown",
        ),
        (
            None,
            None,
            {CONF_IP_ADDRESS: "NotIP"},
            CONF_IP_ADDRESS,
            "invalid_ip_host",
        ),
        (
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID.get_identifier",
            {"side_effect": Exception("connection error")},
            {CONF_IP_ADDRESS: "192.168.1.10"},
            "base",
            "unknown",
        ),
    ],
    ids=[
        "timeout_connect",
        "cannot_connect",
        "http_invalid_response",
        "json_invalid_response",
        "unknown",
        "invalid_ip_host",
        "generic_exception",
    ],
)
async def test_config_flow_errors_recover(
    hass: HomeAssistant,
    patch_target: str | None,
    patch_kwargs: PatchKwargs,
    initial_user_input: UserInput,
    error_key: str,
    expected_error: str,
) -> None:
    """Test config flow error handling and recovery."""
    if patch_target is not None:
        manager = patch(patch_target, **dict(patch_kwargs or {}))
    else:
        manager = contextlib.nullcontext()

    with manager:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=initial_user_input,
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {error_key: expected_error}

    with (
        patch(
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID.get_identifier",
            return_value="0101234567",
        ),
        patch(
            "homeassistant.components.tfa_me.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_IP_ADDRESS: "192.168.1.10"},
        )

    assert result2["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TFA.me Station '192.168.1.10'"


async def test_config_flow_duplicate_entry_aborts(
    hass: HomeAssistant,
) -> None:
    """Test config flow aborts if station is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.10"},
        unique_id="0101234567",
    )
    existing_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID.get_identifier",
        return_value="0101234567",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_IP_ADDRESS: "192.168.1.10"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
