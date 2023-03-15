"""Test Anova config flow."""

from unittest.mock import patch

from anova_wifi import AnovaOffline, AnovaPrecisionCooker, InvalidLogin, NoDevicesFound

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.anova.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import CONF_INPUT, DEVICE_UNIQUE_ID, create_entry


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    with patch(
        "homeassistant.components.anova.config_flow.AnovaApi.authenticate",
    ) as auth_patch, patch(
        "homeassistant.components.anova.config_flow.AnovaApi.get_devices"
    ) as device_patch:
        auth_patch.return_value = True
        device_patch.return_value = [
            AnovaPrecisionCooker(None, DEVICE_UNIQUE_ID, "type_sample", None)
        ]
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_INPUT,
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            "device_key": DEVICE_UNIQUE_ID,
            "jwt": None,
            "type": "type_sample",
        }


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate device."""
    with patch(
        "homeassistant.components.anova.config_flow.AnovaApi.authenticate",
    ) as auth_patch, patch(
        "homeassistant.components.anova.config_flow.AnovaApi.get_devices"
    ) as device_patch:
        auth_patch.return_value = True
        device_patch.return_value = [
            AnovaPrecisionCooker(None, DEVICE_UNIQUE_ID, "type_sample", None)
        ]
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


async def test_flow_cant_reach_anova(hass: HomeAssistant) -> None:
    """Test anova offline throwing error."""
    with patch(
        "homeassistant.components.anova.config_flow.AnovaApi.authenticate",
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
        assert result["errors"] == {"base": "cannot_connect"}


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
        assert result["type"] == data_entry_flow.FlowResultType.FORM
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
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_flow_no_devices(hass: HomeAssistant) -> None:
    """Test unknown error throwing error."""
    with patch(
        "homeassistant.components.anova.config_flow.AnovaApi.authenticate"
    ), patch(
        "homeassistant.components.anova.config_flow.AnovaApi.get_devices",
        side_effect=NoDevicesFound(),
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
        assert result["errors"] == {"base": "no_devices_found"}
