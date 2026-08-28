"""Test the HTML5 config flow."""

import binascii
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.html5.const import (
    ATTR_VAPID_EMAIL,
    ATTR_VAPID_PUB_KEY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ATTR_VAPID_PRV_KEY, MOCK_CONF, MOCK_CONF_PUB_KEY


async def test_step_user_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONF
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **MOCK_CONF,
        ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
        CONF_NAME: DOMAIN,
    }

    assert mock_setup_entry.call_count == 1


async def test_step_user_success_generate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful user config flow, generating a key pair."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.html5.config_flow.vapid_generate_private_key",
        return_value=MOCK_CONF[ATTR_VAPID_PRV_KEY],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {ATTR_VAPID_EMAIL: "test@example.com"}
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **MOCK_CONF,
        ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
        CONF_NAME: DOMAIN,
    }

    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize("exception", [ValueError, binascii.Error])
async def test_step_user_form_invalid_key(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
) -> None:
    """Test invalid user input."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.html5.config_flow.vapid_get_public_key",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONF
        )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"vapid_prv_key": "invalid_prv_key"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONF
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **MOCK_CONF,
        ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
        CONF_NAME: DOMAIN,
    }
    assert mock_setup_entry.call_count == 1
