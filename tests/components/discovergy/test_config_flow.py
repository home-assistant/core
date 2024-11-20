"""Test the Discovergy config flow."""

from unittest.mock import AsyncMock, patch

from pydiscovergy.error import DiscovergyClientError, HTTPError, InvalidLogin
import pytest

from homeassistant.components.discovergy.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, discovergy: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
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

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, discovergy: AsyncMock
) -> None:
    """Test reauth flow."""
    config_entry.add_to_hass(hass)
    init_result = await config_entry.start_reauth_flow(hass)
    assert init_result["type"] is FlowResultType.FORM
    assert init_result["step_id"] == "reauth_confirm"

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

        assert configure_result["type"] is FlowResultType.ABORT
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
async def test_form_fail(
    hass: HomeAssistant, discovergy: AsyncMock, error: Exception, message: str
) -> None:
    """Test to handle exceptions."""
    discovergy.meters.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": message}

    # reset and test for success
    discovergy.meters.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert "errors" not in result
