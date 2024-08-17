"""Tests for the BSBLan device config flow."""

from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANConnectionError
import pytest

from homeassistant.components.bsblan import config_flow
from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

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

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "BSB-LAN - 00:80:41:19:69:90"
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
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


async def test_device_info_not_available(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test handling of device info not being available."""
    mock_bsblan.device.return_value = None
    mock_bsblan.info.return_value = None

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

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_create_entry(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test creating a config entry."""
    mock_device = MagicMock()
    mock_device.name = "Test Device"
    mock_device.MAC = "00:11:22:33:44:55"
    mock_device.version = "1.0.0"

    mock_info = MagicMock()
    mock_info.controller_variant.value = "Test Variant"

    mock_bsblan.device.return_value = mock_device
    mock_bsblan.info.return_value = mock_info

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

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device - 00:11:22:33:44:55"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_create_entry_no_device_info(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test creating a config entry when device_info is not available."""
    mock_bsblan.device.return_value = MagicMock(
        name="Test Device", MAC="00:11:22:33:44:55", version="1.0.0"
    )
    mock_bsblan.info.return_value = MagicMock(
        controller_variant=MagicMock(value="Test Variant")
    )

    flow = config_flow.BSBLANFlowHandler()
    flow.hass = hass
    flow.host = "127.0.0.1"
    flow.port = 80
    flow.passkey = "1234"
    flow.username = "admin"
    flow.password = "admin1234"

    # Simulate a scenario where _get_bsblan_info was not called or failed
    flow.device_info = None

    with pytest.raises(TypeError, match="Device info is not available"):
        await flow._async_create_entry()


async def test_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test we show user form on BSBLan connection error."""
    mock_bsblan.device.side_effect = BSBLANConnectionError

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

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}
    assert result.get("step_id") == "user"


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
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

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
