"""Test VoIP init."""
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry,
    setup_voip,
) -> None:
    """Test adding/removing VoIP."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_user_management(
    hass: HomeAssistant, config_entry, setup_voip, snapshot: SnapshotAssertion
) -> None:
    """Test creating and removing voip user."""
    user = await hass.auth.async_get_user(config_entry.data["user"])
    assert user is not None
    assert user.is_active
    assert user.system_generated
    assert not user.is_admin
    assert user.name == "Voice over IP"
    assert user.groups == snapshot
    assert len(user.credentials) == 0
    assert len(user.refresh_tokens) == 0

    await hass.config_entries.async_remove(config_entry.entry_id)

    assert await hass.auth.async_get_user(user.id) is None
