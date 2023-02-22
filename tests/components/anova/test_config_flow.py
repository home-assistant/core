"""Test Anova config flow."""

from unittest.mock import patch

from anova_wifi import AnovaOffline

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.anova.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import CONF_INPUT, ONLINE_UPDATE, create_entry


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    with patch(
        "homeassistant.components.anova.AnovaPrecisionCooker.update"
    ) as update_patch:
        update_patch.return_value = ONLINE_UPDATE
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == CONF_INPUT


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate device."""
    with patch(
        "homeassistant.components.anova.AnovaPrecisionCooker.update"
    ) as update_patch:
        update_patch.return_value = ONLINE_UPDATE
        create_entry(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_flow_incorrect_id(hass: HomeAssistant) -> None:
    """Test incorrect device id throwing error."""
    with patch(
        "homeassistant.components.anova.AnovaPrecisionCooker.update",
        side_effect=AnovaOffline(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_id"}
