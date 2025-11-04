"""Test the Rejseplanen config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.rejseplanen.const import CONF_API_KEY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user_step(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_success_with_api_validation(hass: HomeAssistant) -> None:
    """Test successful config flow with API validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Mock successful API validation
    with patch(
        "homeassistant.components.rejseplanen.config_flow.Rejseplanen.validate_auth_key",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "valid-test-key"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Rejseplanen"
    assert result2["data"][CONF_API_KEY] == "valid-test-key"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid authentication handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock failed API validation
    with patch(
        "homeassistant.components.rejseplanen.config_flow.Rejseplanen.validate_auth_key",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "invalid-key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_api_connection_exception(hass: HomeAssistant) -> None:
    """Test handling of API connection exception during config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock API connection exception
    with patch(
        "homeassistant.components.rejseplanen.config_flow.Rejseplanen.validate_auth_key",
        side_effect=ConnectionError("Network Timeout"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test-key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_singleton_prevention(hass: HomeAssistant) -> None:
    """Test singleton integration prevents multiple entries."""
    # Add existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "existing-key"},
        title="Rejseplanen",
    )
    existing_entry.add_to_hass(hass)

    # Try to start new config flow - should abort for singleton
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
