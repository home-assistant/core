"""Test the Discovergy config flow."""
from unittest.mock import Mock, patch

from pydiscovergy.error import DiscovergyClientError, HTTPError, InvalidLogin
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.discovergy.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.discovergy.const import GET_METERS


async def test_form(hass: HomeAssistant, mock_meters: Mock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.discovergy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(
    hass: HomeAssistant, mock_meters: Mock, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "unique_id": mock_config_entry.unique_id},
        data=None,
    )

    assert init_result["type"] == data_entry_flow.FlowResultType.FORM
    assert init_result["step_id"] == "reauth"

    with patch(
        "homeassistant.components.discovergy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        configure_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

        assert configure_result["type"] == data_entry_flow.FlowResultType.ABORT
        assert configure_result["reason"] == "reauth_successful"
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (InvalidLogin, "invalid_auth"),
        (HTTPError, "cannot_connect"),
        (DiscovergyClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_fail(hass: HomeAssistant, error: Exception, message: str) -> None:
    """Test to handle exceptions."""

    with patch(
        "pydiscovergy.Discovergy.meters",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": message}

    with patch("pydiscovergy.Discovergy.meters", return_value=GET_METERS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "test@example.com"
        assert "errors" not in result
