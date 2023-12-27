"""Test the huum config flow."""
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.huum.config_flow import CannotConnect
from homeassistant.components.huum.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.huum.config_flow.Huum.status",
        return_value=True,
    ), patch(
        "homeassistant.components.huum.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USERNAME
    assert result2["data"] == {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "raises",
    "error_base",
    (
        (Exception, "unknown"),
        (CannotConnect, "cannot_connect"),
        (aiohttp.ClientError, "invalid_auth"),
    ),
)
async def test_huum_errors(
    hass: HomeAssistant, raises: Exception, error_base: str
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.huum.config_flow.Huum.status",
        side_effect=raises,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": error_base}
