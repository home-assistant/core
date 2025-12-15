"""Test the YoLink Local config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.yolink_local.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.yolink_local.const import CONF_NET_ID, DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NET_ID: "net-id-1234",
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "YoLink Local Hub"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NET_ID: "net-id-1234",
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NET_ID: "net-id-1234",
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NET_ID: "net-id-1234",
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "YoLink Local Hub"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NET_ID: "net-id-1234",
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient.authenticate",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NET_ID: "net-id-1234",
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch(
        "homeassistant.components.yolink_local.config_flow.YoLinkLocalHubClient.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_NET_ID: "net-id-1234",
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "YoLink Local Hub"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_NET_ID: "net-id-1234",
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1
