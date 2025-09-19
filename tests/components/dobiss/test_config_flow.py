"""Test the Dobiss config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.dobiss.config_flow import CannotConnect
from homeassistant.components.dobiss.const import (
    CONF_COVER_CLOSETIME,
    CONF_COVER_SET_END_POSITION,
    CONF_COVER_USE_TIMED,
    CONF_IGNORE_ZIGBEE_DEVICES,
    CONF_INVERT_BINARY_SENSOR,
    CONF_SECRET,
    CONF_SECURE,
    CONF_WEBSOCKET_TIMEOUT,
    DEFAULT_COVER_CLOSETIME,
    DEFAULT_COVER_SET_END_POSITION,
    DEFAULT_COVER_USE_TIMED,
    DEFAULT_IGNORE_ZIGBEE_DEVICES,
    DEFAULT_INVERT_BINARY_SENSOR,
    DEFAULT_WEBSOCKET_TIMEOUT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.asyncio


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.dobiss.config_flow.DobissConnection.authenticate",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "test.host.com",
                CONF_SECRET: "test-secret",
                CONF_SECURE: True,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "NXT server test.host.com"
    assert result2["data"] == {
        CONF_HOST: "test.host.com",
        CONF_SECRET: "test-secret",
        CONF_SECURE: True,
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dobiss.config_flow.DobissConnection.authenticate",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "test.host.com",
                CONF_SECRET: "test-secret",
                CONF_SECURE: True,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {CONF_SECRET: "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dobiss.config_flow.DobissConnection.authenticate",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "test.host.com",
                CONF_SECRET: "test-secret",
                CONF_SECURE: True,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "cannot_connect"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    config_entry = MockConfigEntry(
        entry_id="test",
        domain=DOMAIN,
        title="Test",
        data={
            CONF_HOST: "test.host.com",
            CONF_SECRET: "test-secret",
            CONF_SECURE: True,
        },
        options={},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_COVER_SET_END_POSITION: True,
            CONF_INVERT_BINARY_SENSOR: True,
            CONF_IGNORE_ZIGBEE_DEVICES: True,
            CONF_COVER_CLOSETIME: 30,
            CONF_COVER_USE_TIMED: True,
            CONF_WEBSOCKET_TIMEOUT: 60,
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_COVER_SET_END_POSITION: True,
        CONF_INVERT_BINARY_SENSOR: True,
        CONF_IGNORE_ZIGBEE_DEVICES: True,
        CONF_COVER_CLOSETIME: 30,
        CONF_COVER_USE_TIMED: True,
        CONF_WEBSOCKET_TIMEOUT: 60,
    }


async def test_options_flow_defaults(hass: HomeAssistant) -> None:
    """Test options flow with default values."""
    config_entry = MockConfigEntry(
        entry_id="test",
        domain=DOMAIN,
        title="Test",
        data={
            CONF_HOST: "test.host.com",
            CONF_SECRET: "test-secret",
            CONF_SECURE: True,
        },
        options={},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], result["data_schema"]({})
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_COVER_SET_END_POSITION: DEFAULT_COVER_SET_END_POSITION,
        CONF_INVERT_BINARY_SENSOR: DEFAULT_INVERT_BINARY_SENSOR,
        CONF_IGNORE_ZIGBEE_DEVICES: DEFAULT_IGNORE_ZIGBEE_DEVICES,
        CONF_COVER_CLOSETIME: DEFAULT_COVER_CLOSETIME,
        CONF_COVER_USE_TIMED: DEFAULT_COVER_USE_TIMED,
        CONF_WEBSOCKET_TIMEOUT: DEFAULT_WEBSOCKET_TIMEOUT,
    }
