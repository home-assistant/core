# tests/components/pushmeld/test_config_flow.py
"""Tests for the PushMeld config flow."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.pushmeld.const import CONF_MAXCODE, DEFAULT_NAME, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Create one entry from a MaxCode and a generated title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "test-maxcode"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["result"].unique_id is None
    assert result["data"] == {CONF_MAXCODE: "test-maxcode"}


async def test_user_flow_rejects_empty_maxcode(hass: HomeAssistant) -> None:
    """Require a MaxCode before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MAXCODE: "invalid_maxcode"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "test-maxcode"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_generates_an_available_title(hass: HomeAssistant) -> None:
    """Generate the next title when existing actions and entries use names."""
    hass.services.async_register(NOTIFY_DOMAIN, "pushmeld", AsyncMock())
    unloaded_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{DEFAULT_NAME} 2",
        data={CONF_MAXCODE: "unloaded-maxcode"},
    )
    unloaded_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "new-maxcode"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DEFAULT_NAME} 3"


async def test_user_flow_rejects_duplicate_maxcode(
    hass: HomeAssistant,
) -> None:
    """Do not allow the same MaxCode to be configured more than once."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing channel",
        data={CONF_MAXCODE: "existing-maxcode"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "existing-maxcode"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
