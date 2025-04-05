"""Test the UniFi Access config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.unifi_access.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(autouse=True)
def lock_platform_only():
    """Skip setting up platform to speed up tests."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", []):
        yield


async def test_form(hass: HomeAssistant, mock_async_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.unifi_access.config_flow._validate_input",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_API_TOKEN: "test-api-token",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_API_TOKEN: "test-api-token",
    }


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_async_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    def side_effect(_, __, errors):
        errors["base"] = "invalid_auth"
        return {}

    with patch(
        "homeassistant.components.unifi_access.config_flow._validate_input",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_API_TOKEN: "test-api-token",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.unifi_access.config_flow._validate_input",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_API_TOKEN: "test-api-token",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_API_TOKEN: "test-api-token",
    }


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_async_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    def side_effect(_, __, errors):
        errors["base"] = "cannot_connect"
        return {}

    with patch(
        "homeassistant.components.unifi_access.config_flow._validate_input",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_API_TOKEN: "test-api-token",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.unifi_access.config_flow._validate_input",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_API_TOKEN: "test-api-token",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_API_TOKEN: "test-api-token",
    }
