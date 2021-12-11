"""Tests for the WLED config flow."""
from unittest.mock import MagicMock

from wled import WLEDConnectionError

from homeassistant.components import zeroconf
from homeassistant.components.wled.const import CONF_KEEP_MASTER_LIGHT, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant, mock_wled_config_flow: MagicMock, mock_setup_entry: None
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("title") == "192.168.1.123"
    assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert result["data"][CONF_MAC] == "aabbccddeeff"


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, mock_wled_config_flow: MagicMock, mock_setup_entry: None
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    assert result.get("description_placeholders") == {CONF_NAME: "example"}
    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    flow = flows[0]
    assert "context" in flow
    assert flow["context"][CONF_HOST] == "192.168.1.123"
    assert flow["context"][CONF_NAME] == "example"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2.get("title") == "example"
    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY

    assert "data" in result2
    assert result2["data"][CONF_HOST] == "192.168.1.123"
    assert result2["data"][CONF_MAC] == "aabbccddeeff"


async def test_connection_error(
    hass: HomeAssistant, mock_wled_config_flow: MagicMock
) -> None:
    """Test we show user form on WLED connection error."""
    mock_wled_config_flow.update.side_effect = WLEDConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.com"},
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_zeroconf_connection_error(
    hass: HomeAssistant, mock_wled_config_flow: MagicMock
) -> None:
    """Test we abort zeroconf flow on WLED connection error."""
    mock_wled_config_flow.update.side_effect = WLEDConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "cannot_connect"


async def test_zeroconf_confirm_connection_error(
    hass: HomeAssistant, mock_wled_config_flow: MagicMock
) -> None:
    """Test we abort zeroconf flow on WLED connection error."""
    mock_wled_config_flow.update.side_effect = WLEDConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_ZEROCONF,
            CONF_HOST: "example.com",
            CONF_NAME: "test",
        },
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.com.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "cannot_connect"


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    init_integration: MagicMock,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.123"},
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant,
    init_integration: MagicMock,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_with_mac_device_exists_abort(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "aabbccddeeff"},
            type="mock_type",
        ),
    )

    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "init"
    assert "flow_id" in result

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_KEEP_MASTER_LIGHT: True},
    )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("data") == {
        CONF_KEEP_MASTER_LIGHT: True,
    }
