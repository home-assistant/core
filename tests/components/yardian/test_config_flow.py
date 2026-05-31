"""Test the Yardian config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant import config_entries
from homeassistant.components.yardian.const import DOMAIN, PRODUCT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_yardian_client: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Configure the mock to return the data the test expects
    mock_yardian_client.fetch_device_info.return_value = {
        "name": "fake_name",
        "yid": "fake_yid",
    }

    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.create",
        return_value=mock_yardian_client,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "fake_host", "access_token": "fake_token"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == PRODUCT_NAME
    assert result2["data"] == {
        "host": "fake_host",
        "access_token": "fake_token",
        "name": "fake_name",
        "yid": "fake_yid",
    }


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_yardian_client: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.create",
        side_effect=NotAuthorizedException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "fake_host", "access_token": "fake_token"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # Fix: Return the mock object in the recovery block
    mock_yardian_client.fetch_device_info.return_value = {
        "name": "fake_name",
        "yid": "fake_yid",
    }
    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.create",
        return_value=mock_yardian_client,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "fake_host", "access_token": "fake_token"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_yardian_client: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.create",
        side_effect=NetworkException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "fake_host", "access_token": "fake_token"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Fix: Return the mock object in the recovery block
    mock_yardian_client.fetch_device_info.return_value = {
        "name": "fake_name",
        "yid": "fake_yid",
    }
    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.create",
        return_value=mock_yardian_client,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "fake_host", "access_token": "fake_token"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_uncategorized_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_yardian_client: AsyncMock
) -> None:
    """Test we handle uncategorized error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.create",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "fake_host", "access_token": "fake_token"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    # Fix: Return the mock object in the recovery block
    mock_yardian_client.fetch_device_info.return_value = {
        "name": "fake_name",
        "yid": "fake_yid",
    }
    with patch(
        "homeassistant.components.yardian.config_flow.AsyncYardianClient.create",
        return_value=mock_yardian_client,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "fake_host", "access_token": "fake_token"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
