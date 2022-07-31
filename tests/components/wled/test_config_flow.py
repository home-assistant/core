"""Tests for the WLED config flow."""
from unittest.mock import AsyncMock, MagicMock

from wled import WLEDConnectionError

from homeassistant.components import zeroconf
from homeassistant.components.wled.const import CONF_KEEP_MASTER_LIGHT, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant, mock_wled_config_flow: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.123"}
    )

    assert result.get("title") == "WLED RGB Light"
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.123"
    assert "result" in result
    assert result["result"].unique_id == "aabbccddeeff"


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, mock_wled_config_flow: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            addresses=["192.168.1.123"],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "aabbccddeeff"},
            type="mock_type",
        ),
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    assert (
        flows[0].get("context", {}).get("configuration_url") == "http://192.168.1.123"
    )
    assert result.get("description_placeholders") == {CONF_NAME: "WLED RGB Light"}
    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("type") == FlowResultType.FORM
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2.get("title") == "WLED RGB Light"
    assert result2.get("type") == FlowResultType.CREATE_ENTRY

    assert "data" in result2
    assert result2["data"][CONF_HOST] == "192.168.1.123"
    assert "result" in result2
    assert result2["result"].unique_id == "aabbccddeeff"


async def test_zeroconf_during_onboarding(
    hass: HomeAssistant,
    mock_wled_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_onboarding: MagicMock,
) -> None:
    """Test we create a config entry when discovered during onboarding."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            addresses=["192.168.1.123"],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "aabbccddeeff"},
            type="mock_type",
        ),
    )

    assert result.get("title") == "WLED RGB Light"
    assert result.get("type") == FlowResultType.CREATE_ENTRY

    assert result.get("data") == {CONF_HOST: "192.168.1.123"}
    assert "result" in result
    assert result["result"].unique_id == "aabbccddeeff"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


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

    assert result.get("type") == FlowResultType.FORM
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
            addresses=["192.168.1.123"],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "aabbccddeeff"},
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.123"},
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_user_with_cct_channel_abort(
    hass: HomeAssistant,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort user flow if WLED device uses a CCT channel."""
    mock_wled_config_flow.update.return_value.info.leds.cct = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.123"},
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "cct_unsupported"


async def test_zeroconf_without_mac_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            addresses=["192.168.1.123"],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_with_mac_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if WLED device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            addresses=["192.168.1.123"],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "aabbccddeeff"},
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_with_cct_channel_abort(
    hass: HomeAssistant,
    mock_wled_config_flow: MagicMock,
) -> None:
    """Test we abort zeroconf flow if WLED device uses a CCT channel."""
    mock_wled_config_flow.update.return_value.info.leds.cct = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.123",
            addresses=["192.168.1.123"],
            hostname="example.local.",
            name="mock_name",
            port=None,
            properties={CONF_MAC: "aabbccddeeff"},
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "cct_unsupported"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert "flow_id" in result

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_KEEP_MASTER_LIGHT: True},
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {
        CONF_KEEP_MASTER_LIGHT: True,
    }
