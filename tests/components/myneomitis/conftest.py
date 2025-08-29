"""conftest.py for myneomitis integration tests."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import event


# Auto-enable integrations in Home Assistant tests
@pytest.fixture(autouse=True)
def enable_my_integrations(enable_integrations) -> None:
    """Auto-use the enable_integrations fixture from homeassistant-component plugin.

    This allows loading of the myneomitis integration in tests.
    """
    return


@pytest.fixture(autouse=True)
def disable_ha_helpers(monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant) -> None:
    """Disable global timer and stub async_entries for all calls."""
    monkeypatch.setattr(
        event, "track_time_interval", lambda hass, action, interval: None
    )
    monkeypatch.setattr(
        hass.config_entries, "async_entries", lambda *args, **kwargs: []
    )
