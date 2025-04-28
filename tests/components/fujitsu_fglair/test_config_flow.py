"""Test the Fujitsu HVAC (based on Ayla IOT) config flow."""

from unittest.mock import AsyncMock

from ayla_iot_unofficial import AylaAuthError
import pytest

from homeassistant.components.fujitsu_fglair.const import (
    CONF_REGION,
    DOMAIN,
    REGION_DEFAULT,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from .conftest import TEST_PASSWORD, TEST_PASSWORD2, TEST_USERNAME

from tests.common import MockConfigEntry


async def _initial_step(hass: HomeAssistant) -> FlowResult:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_REGION: REGION_DEFAULT,
        },
    )


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ayla_api: AsyncMock
) -> None:
    """Test full config flow."""
    result = await _initial_step(hass)
    mock_ayla_api.async_sign_in.assert_called_once()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"FGLair ({TEST_USERNAME})"
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_REGION: REGION_DEFAULT,
    }


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that re-adding the same account fails."""
    mock_config_entry.add_to_hass(hass)
    result = await _initial_step(hass)
    mock_ayla_api.async_sign_in.assert_not_called()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "err_msg"),
    [
        (AylaAuthError, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ayla_api: AsyncMock,
    exception: Exception,
    err_msg: str,
) -> None:
    """Test we handle exceptions."""

    mock_ayla_api.async_sign_in.side_effect = exception
    result = await _initial_step(hass)
    mock_ayla_api.async_sign_in.assert_called_once()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": err_msg}

    mock_ayla_api.async_sign_in.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_REGION: REGION_DEFAULT,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"FGLair ({TEST_USERNAME})"
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_REGION: REGION_DEFAULT,
    }


async def test_reauth_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: TEST_PASSWORD2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD2


@pytest.mark.parametrize(
    ("exception", "err_msg"),
    [
        (AylaAuthError, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    err_msg: str,
    mock_setup_entry: AsyncMock,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow when an exception occurs."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_ayla_api.async_sign_in.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: TEST_PASSWORD2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": err_msg}

    mock_ayla_api.async_sign_in.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: TEST_PASSWORD2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD2
