"""Test the TFA.me integration: test of config_flow.py."""

from __future__ import annotations

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

from .conftest import FAKE_JSON

from tests.common import MockConfigEntry


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the flow starts with the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (
            TFAmeTimeoutError("timeout"),
            "timeout_connect",
        ),
        (
            TFAmeConnectionError("connection error"),
            "cannot_connect",
        ),
        (
            TFAmeHTTPError("HTTP error"),
            "invalid_response",
        ),
        (
            TFAmeJSONError("JSON error"),
            "invalid_response",
        ),
        (
            TFAmeException("unknown"),
            "unknown",
        ),
        (
            Exception("unexpected error"),
            "unknown",
        ),
    ],
    ids=[
        "timeout_connect",
        "cannot_connect",
        "http_invalid_response",
        "json_invalid_response",
        "unknown",
        "generic_exception",
    ],
)
async def test_config_flow_errors_recover(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test config flow error handling and recovery."""
    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeClient.async_get_sensors",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_IP_ADDRESS: "192.168.0.10"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    with (
        patch(
            "homeassistant.components.tfa_me.config_flow.TFAmeClient.async_get_sensors",
            return_value=FAKE_JSON,
        ),
        patch(
            "homeassistant.components.tfa_me.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_IP_ADDRESS: "192.168.1.10"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "TFA.me Station '05B3E4E44'"
    assert result["data"] == {CONF_IP_ADDRESS: "192.168.1.10"}


async def test_config_flow_duplicate_entry_aborts(
    hass: HomeAssistant,
) -> None:
    """Test config flow aborts if station is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.10"},
        unique_id="05b3e4e44",
    )
    existing_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeClient.async_get_sensors",
        return_value=FAKE_JSON,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_IP_ADDRESS: "192.168.1.10"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_invalid_ip_host(
    hass: HomeAssistant,
) -> None:
    """Test config flow rejects invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_IP_ADDRESS: "NotIP"},
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_IP_ADDRESS: "invalid_ip_host"}


async def test_existing_entry_updates_host(
    hass: HomeAssistant,
    tfa_me_config_entry: MockConfigEntry,
) -> None:
    """Test an existing entry is updated with a newly validated host."""
    identifier = str(FAKE_JSON["gateway_id"]).lower()
    new_host = "192.168.1.42"

    hass.config_entries.async_update_entry(
        tfa_me_config_entry,
        unique_id=identifier,
    )

    old_host = tfa_me_config_entry.data[CONF_IP_ADDRESS]
    assert old_host != new_host

    with (
        patch(
            "homeassistant.components.tfa_me.config_flow.resolve_tfa_host",
            return_value=new_host,
        ),
        patch(
            "homeassistant.components.tfa_me.config_flow.TFAmeClient.async_get_sensors",
            return_value=FAKE_JSON,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_IP_ADDRESS: new_host},
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert tfa_me_config_entry.data[CONF_IP_ADDRESS] == new_host


async def test_user_station_id(
    hass: HomeAssistant,
) -> None:
    """Test setup using a station ID."""
    with patch(
        "homeassistant.components.tfa_me.config_flow.TFAmeClient.async_get_sensors",
        return_value=FAKE_JSON,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_IP_ADDRESS: "05B-3E4-E44"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_IP_ADDRESS: "tfa-me-05b-3e4-e44.local"}
