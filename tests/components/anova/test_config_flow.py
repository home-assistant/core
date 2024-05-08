"""Test Anova config flow."""

from unittest.mock import patch

from anova_wifi import AnovaApi, InvalidLogin

from homeassistant import config_entries
from homeassistant.components.anova.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONF_INPUT


async def test_flow_user(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "sample@gmail.com",
        CONF_PASSWORD: "sample",
        CONF_DEVICES: [],
    }


async def test_flow_wrong_login(hass: HomeAssistant) -> None:
    """Test incorrect login throwing error."""
    with patch(
        "homeassistant.components.anova.config_flow.AnovaApi.authenticate",
        side_effect=InvalidLogin,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error throwing error."""
    with patch(
        "homeassistant.components.anova.config_flow.AnovaApi.authenticate",
        side_effect=Exception(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
