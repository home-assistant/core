"""Test the Fujitsu HVAC (based on Ayla IOT) config flow."""

from unittest.mock import AsyncMock

from ayla_iot_unofficial import AylaAuthError
import pytest

from homeassistant import config_entries
from homeassistant.components.fujitsu_hvac.const import CONF_EUROPE, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from .conftest import TEST_PASSWORD, TEST_PASSWORD2, TEST_USERNAME, TEST_USERNAME2

from tests.common import MockConfigEntry


async def _initial_step(hass: HomeAssistant) -> FlowResult:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_EUROPE: False,
        },
    )
    await hass.async_block_till_done()
    return result


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_ayla_api: AsyncMock
) -> None:
    """Test full config flow."""
    result = await _initial_step(hass)
    mock_ayla_api.async_sign_in.assert_called_once()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Fujitsu HVAC ({TEST_USERNAME})"
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_EUROPE: False,
    }


@pytest.mark.parametrize(
    ("mock_ayla_api", "errmsg"),
    [
        (AylaAuthError, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
    indirect=["mock_ayla_api"],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ayla_api: AsyncMock,
    errmsg: str,
) -> None:
    """Test we handle exceptions."""

    result = await _initial_step(hass)
    mock_ayla_api.async_sign_in.assert_called_once()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": errmsg}

    mock_ayla_api.async_sign_in.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_EUROPE: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Fujitsu HVAC ({TEST_USERNAME})"
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_EUROPE: False,
    }


async def test_reauth_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data={},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD2,
            CONF_EUROPE: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD2


async def test_reauth_different_username(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_ayla_api: AsyncMock,
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data={},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME2,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_EUROPE: False,
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
