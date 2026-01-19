"""Test the Energy Tracker config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from tests.common import MockConfigEntry

from homeassistant.components.energy_tracker.const import CONF_API_TOKEN, DOMAIN


async def test_user_form_create_entry(hass: HomeAssistant) -> None:
    """Test creating a new config entry via user flow."""
    # Arrange
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Act
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "John's Account",
            CONF_API_TOKEN: "test-token-123",
        },
    )

    # Assert
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "John's Account"
    assert result2["data"] == {
        CONF_API_TOKEN: "test-token-123",
    }


async def test_user_form_duplicate_token(hass: HomeAssistant) -> None:
    """Test abort when token already configured."""
    # Arrange
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Energy Tracker",
        data={CONF_API_TOKEN: "duplicate-token"},
        unique_id="duplicate-token",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Act
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Account",
            CONF_API_TOKEN: "duplicate-token",
        },
    )

    # Assert
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reconfigure_form_update_token(hass: HomeAssistant) -> None:
    """Test reconfiguring to update the token."""
    # Arrange
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Energy Tracker",
        data={CONF_API_TOKEN: "old-token"},
        unique_id="old-token",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reconfigure",
            "entry_id": entry.entry_id,
        },
    )

    # Act
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "new-token-456",
            },
        )

    # Assert
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_API_TOKEN: "new-token-456",
    }
    assert entry.unique_id == "new-token-456"
    mock_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_form_duplicate_token(hass: HomeAssistant) -> None:
    """Test abort when reconfigure token conflicts with another entry."""
    # Arrange
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="Energy Tracker",
        data={CONF_API_TOKEN: "token-1"},
        unique_id="token-1",
    )
    entry1.add_to_hass(hass)

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        title="Energy Tracker",
        data={CONF_API_TOKEN: "token-2"},
        unique_id="token-2",
    )
    entry2.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reconfigure",
            "entry_id": entry2.entry_id,
        },
    )

    # Act
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "token-1",
        },
    )

    # Assert
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
