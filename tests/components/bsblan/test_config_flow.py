"""Tests for the BSBLan device config flow."""
from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANConnectionError

from homeassistant import data_entry_flow
from homeassistant.components.bsblan import config_flow
from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_bsblan_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == format_mac("00:80:41:19:69:90")
    assert result2.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }
    assert "result" in result2
    assert result2["result"].unique_id == format_mac("00:80:41:19:69:90")

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan_config_flow.device.mock_calls) == 1


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_connection_error(
    hass: HomeAssistant,
    mock_bsblan_config_flow: MagicMock,
) -> None:
    """Test we show user form on BSBLan connection error."""
    mock_bsblan_config_flow.device.side_effect = BSBLANConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("errors") == {"base": "cannot_connect"}
    assert result.get("step_id") == "user"


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_bsblan_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort flow if BSBLAN device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"
