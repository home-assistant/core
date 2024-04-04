"""Test the PoolSense config flow."""

from unittest.mock import patch

from homeassistant.components.poolsense.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test we handle invalid credentials."""
    with patch(
        "poolsense.PoolSense.test_poolsense_credentials",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_valid_credentials(hass: HomeAssistant) -> None:
    """Test we handle invalid credentials."""
    with (
        patch("poolsense.PoolSense.test_poolsense_credentials", return_value=True),
        patch(
            "homeassistant.components.poolsense.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"

    assert len(mock_setup_entry.mock_calls) == 1
