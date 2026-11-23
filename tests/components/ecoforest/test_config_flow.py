"""Test the Ecoforest config flow."""

from unittest.mock import AsyncMock, Mock, patch

from pyecoforest.exceptions import EcoforestAuthenticationRequired
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant import config_entries
from homeassistant.components.ecoforest.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_device, config
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "pyecoforest.api.EcoforestApi.get",
        return_value=mock_device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "result" in result
    assert result["result"].unique_id == "1234"
    assert result["title"] == "Ecoforest 1234"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_device_already_configured(
    hass: HomeAssistant, config_entry, mock_device, config
) -> None:
    """Test device already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "pyecoforest.api.EcoforestApi.get",
        return_value=mock_device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            EcoforestAuthenticationRequired("401"),
            "invalid_auth",
        ),
        (
            Exception("Something wrong"),
            "cannot_connect",
        ),
    ],
)
async def test_flow_fails(
    hass: HomeAssistant, error: Exception, message: str, mock_device, config
) -> None:
    """Test we handle failed flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyecoforest.api.EcoforestApi.get",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": message}

    with patch(
        "pyecoforest.api.EcoforestApi.get",
        return_value=mock_device,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    mock_device: Mock,
) -> None:
    """Test a successful reauthentication."""
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert get_schema_suggested_value(result["data_schema"].schema, CONF_USERNAME) == (
        "test-username"
    )

    with patch("pyecoforest.api.EcoforestApi.get", return_value=mock_device):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "message"),
    [
        pytest.param(
            EcoforestAuthenticationRequired("401"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(Exception("Something wrong"), "cannot_connect", id="exception"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    mock_device: Mock,
    error: Exception,
    message: str,
) -> None:
    """Test reauthentication errors and a successful retry."""
    result = await config_entry.start_reauth_flow(hass)

    with patch("pyecoforest.api.EcoforestApi.get", side_effect=error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "wrong-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": message}
    assert get_schema_suggested_value(result["data_schema"].schema, CONF_USERNAME) == (
        "new-username"
    )

    with patch("pyecoforest.api.EcoforestApi.get", return_value=mock_device):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "new-password"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_wrong_device(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_device: Mock
) -> None:
    """Test reauthentication aborts for a different device."""
    result = await config_entry.start_reauth_flow(hass)
    mock_device.serial_number = "5678"

    with patch("pyecoforest.api.EcoforestApi.get", return_value=mock_device):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test-username", CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert config_entry.data[CONF_PASSWORD] == "test-password"
