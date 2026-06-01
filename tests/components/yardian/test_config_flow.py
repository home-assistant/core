"""Test the Yardian config flow."""

from unittest.mock import AsyncMock

import pytest
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant.components.yardian.const import DOMAIN, PRODUCT_NAME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_yardian_client")


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "fake_host", "access_token": "fake_token"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == PRODUCT_NAME
    assert result["data"] == {
        "host": "fake_host",
        "access_token": "fake_token",
        "name": "fake_name",
        "yid": "fake_yid",
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NotAuthorizedException, "invalid_auth"),
        (NetworkException, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors and recover."""
    mock_yardian_client.fetch_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "fake_host", "access_token": "fake_token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_yardian_client.fetch_device_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "fake_host", "access_token": "fake_token"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
