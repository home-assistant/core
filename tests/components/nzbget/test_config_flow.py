"""Test the NZBGet config flow."""

from unittest.mock import patch

from pynzbgetapi import NZBGetAPIException

from homeassistant.components.nzbget.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    ENTRY_CONFIG,
    USER_INPUT,
    _patch_async_setup_entry,
    _patch_history,
    _patch_status,
    _patch_version,
)

from tests.common import MockConfigEntry


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user initiated form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        _patch_version(),
        _patch_status(),
        _patch_history(),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.10.30"
    assert result["data"] == {**USER_INPUT, CONF_VERIFY_SSL: False}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_show_advanced_options(hass: HomeAssistant) -> None:
    """Test we get the user initiated form with advanced options shown."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    user_input_advanced = {
        **USER_INPUT,
        CONF_VERIFY_SSL: True,
    }

    with (
        _patch_version(),
        _patch_status(),
        _patch_history(),
        _patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input_advanced,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.10.30"
    assert result["data"] == {**USER_INPUT, CONF_VERIFY_SSL: True}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nzbget.coordinator.NZBGetAPI.version",
        side_effect=NZBGetAPIException(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nzbget.coordinator.NZBGetAPI.version",
        side_effect=Exception(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_user_form_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that configuring more than one instance is rejected."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
