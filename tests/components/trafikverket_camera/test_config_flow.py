"""Test the Trafikverket Camera config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.trafikverket_camera.const import CONF_LOCATION, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_camera",
    ), patch(
        "homeassistant.components.trafikverket_camera.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "Test location",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test location"
    assert result2["data"] == {
        "api_key": "1234567890",
        "location": "Test location",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert result2["result"].unique_id == "trafikverket_camera-Test location"


@pytest.mark.parametrize(
    ("error_message", "base_error"),
    [
        (
            "Source: Security, message: Invalid authentication",
            "invalid_auth",
        ),
        (
            "Could not find a camera with the specified name",
            "invalid_location",
        ),
        (
            "Found multiple camera with the specified name",
            "more_locations",
        ),
        (
            "Unknown",
            "cannot_connect",
        ),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, error_message: str, base_error: str
) -> None:
    """Test config flow errors."""
    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_camera",
        side_effect=ValueError(error_message),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={
                CONF_API_KEY: "1234567890",
                CONF_LOCATION: "incorrect",
            },
        )

    assert result4["errors"] == {"base": base_error}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_LOCATION: "Test location",
        },
        unique_id="1234",
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
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_camera",
    ), patch(
        "homeassistant.components.trafikverket_camera.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "location": "Test location",
    }


@pytest.mark.parametrize(
    ("sideeffect", "p_error"),
    [
        (
            "Source: Security, message: Invalid authentication",
            "invalid_auth",
        ),
        (
            "Could not find a camera with the specified name",
            "invalid_location",
        ),
        (
            "Found multiple camera with the specified name",
            "more_locations",
        ),
        (
            "Unknown",
            "cannot_connect",
        ),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant, sideeffect: Exception, p_error: str
) -> None:
    """Test a reauthentication flow with error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "1234567890",
            CONF_LOCATION: "Test location",
        },
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()

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
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_camera",
        side_effect=ValueError(sideeffect),
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
        "homeassistant.components.trafikverket_camera.config_flow.TrafikverketCamera.async_get_camera",
    ), patch(
        "homeassistant.components.trafikverket_camera.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "1234567891"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "api_key": "1234567891",
        "location": "Test location",
    }
