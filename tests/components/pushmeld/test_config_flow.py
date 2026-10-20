# tests/components/pushmeld/test_config_flow.py
"""Tests for the PushMeld config flow."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.pushmeld.const import CONF_MAXCODE, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Create one entry from a MaxCode and a local service name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "test-maxcode", CONF_NAME: "Test channel"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test channel"
    assert result["data"] == {
        CONF_MAXCODE: "test-maxcode",
        CONF_NAME: "Test channel",
    }


async def test_user_flow_rejects_empty_name(hass: HomeAssistant) -> None:
    """Require a local service name before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "test-maxcode", CONF_NAME: "   "},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_NAME: "invalid_name"}


async def test_user_flow_rejects_empty_maxcode(hass: HomeAssistant) -> None:
    """Require a MaxCode before creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "", CONF_NAME: "Test channel"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MAXCODE: "invalid_maxcode"}


async def test_user_flow_rejects_duplicate_service_name(
    hass: HomeAssistant,
) -> None:
    """Do not allow two entries to register the same local service."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAXCODE: "existing-maxcode", CONF_NAME: "Test channel"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "new-maxcode", CONF_NAME: "test_channel"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_user_flow_rejects_duplicate_unique_id(
    hass: HomeAssistant,
) -> None:
    """Use Home Assistant's unique-entry guard for existing entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_channel",
        data={CONF_MAXCODE: "existing-maxcode", CONF_NAME: "Legacy channel"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAXCODE: "new-maxcode", CONF_NAME: "Test channel"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
