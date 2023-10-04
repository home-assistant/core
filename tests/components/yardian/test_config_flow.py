"""Test the Yardian config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant import config_entries
from homeassistant.components.yardian.const import DOMAIN, PRODUCT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.fetch_device_info",
        return_value={"name": "fake_name", "yid": "fake_yid"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "fake_host",
                "access_token": "fake_token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == PRODUCT_NAME
    assert result2["data"] == {
        "host": "fake_host",
        "access_token": "fake_token",
        "name": "fake_name",
        "yid": "fake_yid",
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
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.fetch_device_info",
        side_effect=NotAuthorizedException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "fake_host",
                "access_token": "fake_token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # Should be recoverable after hits error
    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.fetch_device_info",
        return_value={"name": "fake_name", "yid": "fake_yid"},
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "fake_host",
                "access_token": "fake_token",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == PRODUCT_NAME
    assert result3["data"] == {
        "host": "fake_host",
        "access_token": "fake_token",
        "name": "fake_name",
        "yid": "fake_yid",
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
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.fetch_device_info",
        side_effect=NetworkException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "fake_host",
                "access_token": "fake_token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Should be recoverable after hits error
    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.fetch_device_info",
        return_value={"name": "fake_name", "yid": "fake_yid"},
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "fake_host",
                "access_token": "fake_token",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == PRODUCT_NAME
    assert result3["data"] == {
        "host": "fake_host",
        "access_token": "fake_token",
        "name": "fake_name",
        "yid": "fake_yid",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_uncategorized_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle uncategorized error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.fetch_device_info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "fake_host",
                "access_token": "fake_token",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    # Should be recoverable after hits error
    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.fetch_device_info",
        return_value={"name": "fake_name", "yid": "fake_yid"},
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "fake_host",
                "access_token": "fake_token",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == PRODUCT_NAME
    assert result3["data"] == {
        "host": "fake_host",
        "access_token": "fake_token",
        "name": "fake_name",
        "yid": "fake_yid",
    }
    assert len(mock_setup_entry.mock_calls) == 1
