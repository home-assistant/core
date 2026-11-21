"""Tests for one-time family import sessions."""

from broadlink_magic import Family

from homeassistant.components.broadlink_magic_home.import_session import (
    ImportSessionManager,
    get_import_manager,
)
from homeassistant.core import HomeAssistant


def test_expired_and_removed_sessions() -> None:
    """Test expiration, rejection, and explicit removal."""
    manager = ImportSessionManager()
    assert manager.get("unknown") is None

    session = manager.create()
    session.created_at = 0
    assert session.complete([Family("family", "Home", "00010203")]) is False
    assert manager.get(session.project_id) is None
    assert manager.active_sessions == ()

    session = manager.create()
    manager.remove(session.project_id)
    assert session.event.is_set()
    assert manager.active_sessions == ()
    assert session.complete([Family("family", "Home", "00010203")]) is False
    assert session.families is None


def test_shared_manager(hass: HomeAssistant) -> None:
    """Test the same manager is reused for a Home Assistant instance."""
    assert get_import_manager(hass) is get_import_manager(hass)
