"""conftest.py for myneomitis integration tests."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import event


@pytest.fixture(autouse=True)
def disable_ha_helpers(monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant) -> None:
    """Disable global timer and stub async_entries for all calls."""
    monkeypatch.setattr(
        event, "track_time_interval", lambda hass, action, interval: None
    )
    monkeypatch.setattr(
        hass.config_entries, "async_entries", lambda *args, **kwargs: []
    )
