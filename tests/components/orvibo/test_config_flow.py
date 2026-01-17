"""Test the Orvibo config flow."""

from unittest.mock import MagicMock, patch

from orvibo.s20 import S20Exception

from homeassistant import config_entries
from homeassistant.components.orvibo.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MODULE = "homeassistant.components.orvibo.config_flow.S20"


async def test_user_step_invalid_host(hass: HomeAssistant) -> None:
    """Test we show invalid_host error when entering an invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "__INVALID_HOST__", CONF_MAC: "AA:BB:CC:DD:EE:FF"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_host"}


async def test_user_step_invalid_mac_address(hass: HomeAssistant) -> None:
    """Test we show invalid_mac error when entering an invalid mac address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.2.3.4", CONF_MAC: "__INVALID_MAC__"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_mac"}


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test we show cannot_connect error on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        MODULE,
        side_effect=S20Exception("fail"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_MAC: "AA:BB:CC:DD:EE:FF"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_step_unexpected_error(hass: HomeAssistant) -> None:
    """Test we show cannot_connect error on unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        MODULE,
        side_effect=Exception("fail"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_MAC: "AA:BB:CC:DD:EE:FF"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(MODULE, return_value=MagicMock()),
        patch(
            "homeassistant.components.orvibo.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_MAC: "AA:BB:CC:DD:EE:FF"}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_NAME
    assert result2["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert len(mock_setup_entry.mock_calls) == 1
