"""Test the TFA.me integration: test of config_flow.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from __future__ import annotations

import contextlib
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tfa_me.const import CONF_NAME_WITH_STATION_ID, DOMAIN
from homeassistant.components.tfa_me.data import TFAmeException
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo


@pytest.mark.asyncio
async def test_show_form(hass: HomeAssistant) -> None:
    """Test: Flow starts with form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "patch_target",
        "patch_kwargs",
        "initial_user_input",
        "error_key",
        "expected_error",
        "check_in_values",
    ),
    [
        (  # 1) TFAmeException raised -> error stored under "base"
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID",
            {"side_effect": TFAmeException("host_empty")},
            {
                CONF_IP_ADDRESS: "192.168.0.10",
                CONF_NAME_WITH_STATION_ID: True,
            },
            "base",
            "host_empty",
            False,
        ),
        (  # 2) Invalid IP/hostname -> error stored under CONF_IP_ADDRESS
            None,
            None,
            {
                CONF_IP_ADDRESS: "NotIP",
                CONF_NAME_WITH_STATION_ID: False,
            },
            CONF_IP_ADDRESS,
            "invalid_ip_host",
            False,
        ),
        (  # 3) Invalid CONF_NAME_WITH_STATION_ID type -> only the value matters
            None,
            None,
            {
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_NAME_WITH_STATION_ID: 123,  # wrong value type
            },
            None,  # key is not relevant here
            "invalid_name_with_station_id",
            True,  # check error via values()
        ),
        (  # 4) Generic exception while connecting -> error on "base"
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID.get_identifier",
            {"side_effect": Exception("connection error")},
            {
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_NAME_WITH_STATION_ID: True,
            },
            "base",
            ("cannot_connect", "unknown"),  # both are allowed
            False,
        ),
    ],
    ids=[
        "tfa_exception_host_empty",
        "invalid_ip_host",
        "invalid_name_with_station_id",
        "cannot_connect",
    ],
)
async def test_config_flow_errors_recover(
    hass: HomeAssistant,
    patch_target,
    patch_kwargs,
    initial_user_input,
    error_key,
    expected_error,
    check_in_values,
) -> None:
    """Test all error cases of the config flow and ensure recovery to CREATE_ENTRY."""

    # Optional patch to simulate specific failure mode
    if patch_target is not None:
        cm = patch(patch_target, **(patch_kwargs or {}))
    else:
        cm = contextlib.nullcontext()

    # Step 1: Trigger the error on initial init
    with cm:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=initial_user_input,
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM

    # Validate the error reported by the flow
    if check_in_values:
        # We only care that the expected_error appears in the error values
        if isinstance(expected_error, tuple):
            assert any(v in expected_error for v in result["errors"].values())
        else:
            assert expected_error in result["errors"].values()
    else:
        # We expect a specific key to be present with a specific value (or one of several)
        assert error_key in result["errors"]
        if isinstance(expected_error, tuple):
            assert result["errors"][error_key] in expected_error
        else:
            assert result["errors"][error_key] == expected_error

    # Step 2: User corrects the input and retries
    with (
        patch(
            "homeassistant.components.tfa_me.config_flow.TFAmeUniqueID.get_identifier",
            return_value="192.168.1.10",
        ),
        patch(
            "homeassistant.components.tfa_me.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_IP_ADDRESS: "192.168.1.10",
                CONF_NAME_WITH_STATION_ID: True,
            },
        )

    # Step 3: Ensure the flow recovers and creates an entry
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TFA.me Station '192.168.1.10'"


def _get_default_from_schema(schema: vol.Schema, key: str) -> Any:
    """Extract (and evaluate) default value for a key in a voluptuous schema."""
    for marker in schema.schema:
        if getattr(marker, "schema", None) == key:
            default = getattr(marker, "default", vol.UNDEFINED)

            # HA/voluptuous may store defaults as callables (default_factory)
            if callable(default):
                return default()

            return default
    raise AssertionError(f"Key {key} not found in schema")


async def test_zeroconf_prefills_user_form_with_host(hass: HomeAssistant) -> None:
    """Zeroconf discovery should jump to user step and prefill host field."""
    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.1.50",
        ip_addresses=["192.168.1.50"],
        port=80,
        hostname="tfa-me-99f-fff-f9d.local.",
        type="_tfa_me._tcp.local.",
        name="tfa_mdns_instance._tfa_me._tcp.local.",
        properties={
            "api": "local",
            "fw": "6.1128",
            "manufacturer": "TFA/Dostmann",
            "model": "TFA.me station type 99",
            "id": "99FFFFF9D",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "data_schema" in result

    schema: vol.Schema = result["data_schema"]

    default_host = _get_default_from_schema(schema, CONF_IP_ADDRESS)
    assert default_host == "192.168.1.50 or 99F-FFF-F9D"
