"""Test the Komfovent config flow."""
from unittest.mock import AsyncMock, patch

import komfovent_api
import pytest

from homeassistant import config_entries
from homeassistant.components.komfovent.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test flow completes as expected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    final_result = await __test_normal_flow(hass, result["flow_id"])
    assert final_result["type"] == FlowResultType.CREATE_ENTRY
    assert final_result["title"] == "test-name"
    assert final_result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "expected_response"),
    [
        (komfovent_api.KomfoventConnectionResult.NOT_FOUND, "cannot_connect"),
        (komfovent_api.KomfoventConnectionResult.UNAUTHORISED, "invalid_auth"),
        (komfovent_api.KomfoventConnectionResult.INVALID_INPUT, "invalid_input"),
    ],
)
async def test_flow_error_authenticating(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    error: komfovent_api.KomfoventConnectionResult,
    expected_response: str,
) -> None:
    """Test errors during flow authentication step are handled and dont affect final result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_credentials",
        return_value=(
            error,
            None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_response}

    final_result = await __test_normal_flow(hass, result2["flow_id"])
    assert final_result["type"] == FlowResultType.CREATE_ENTRY
    assert final_result["title"] == "test-name"
    assert final_result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "expected_response"),
    [
        (komfovent_api.KomfoventConnectionResult.NOT_FOUND, "cannot_connect"),
        (komfovent_api.KomfoventConnectionResult.UNAUTHORISED, "invalid_auth"),
        (komfovent_api.KomfoventConnectionResult.INVALID_INPUT, "invalid_input"),
    ],
)
async def test_flow_error_device_info(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    error: komfovent_api.KomfoventConnectionResult,
    expected_response: str,
) -> None:
    """Test errors during flow device info download step are handled and dont affect final result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_credentials",
        return_value=(
            komfovent_api.KomfoventConnectionResult.SUCCESS,
            komfovent_api.KomfoventCredentials("1.1.1.1", "user", "pass"),
        ),
    ), patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_settings",
        return_value=(
            error,
            None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_response}

    final_result = await __test_normal_flow(hass, result2["flow_id"])
    assert final_result["type"] == FlowResultType.CREATE_ENTRY
    assert final_result["title"] == "test-name"
    assert final_result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_device_already_exists(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test device is not added when it already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        unique_id="test-uid",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    final_result = await __test_normal_flow(hass, result["flow_id"])
    assert final_result["type"] == FlowResultType.ABORT
    assert final_result["reason"] == "already_configured"


async def __test_normal_flow(hass: HomeAssistant, flow_id: str) -> FlowResult:
    """Test flow completing as expected, no matter what happened before."""

    with patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_credentials",
        return_value=(
            komfovent_api.KomfoventConnectionResult.SUCCESS,
            komfovent_api.KomfoventCredentials("1.1.1.1", "user", "pass"),
        ),
    ), patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_settings",
        return_value=(
            komfovent_api.KomfoventConnectionResult.SUCCESS,
            komfovent_api.KomfoventSettings("test-name", None, None, "test-uid"),
        ),
    ):
        final_result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    return final_result
