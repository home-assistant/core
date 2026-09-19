"""Test the Immich Frames config flow."""

from homeassistant.components.immich_frames.const import (
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_user_requires_immich(hass: HomeAssistant) -> None:
    """Test that a parent Immich entry is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "immich_required"


async def test_user_creates_frame(
    hass: HomeAssistant, parent_immich_entry: MockConfigEntry
) -> None:
    """Test creating a frame linked to a loaded Immich entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
            CONF_FRAME_NAME: "Living room",
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Living room"
    assert result["data"] == {
        CONF_IMMICH_ENTRY_ID: parent_immich_entry.entry_id,
        CONF_FRAME_NAME: "Living room",
    }


async def test_user_aborts_when_immich_is_not_loaded(hass: HomeAssistant) -> None:
    """Test that an unavailable parent entry is not offered."""
    MockConfigEntry(domain="immich", state=ConfigEntryState.SETUP_ERROR).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "immich_not_ready"
