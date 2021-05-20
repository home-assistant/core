"""Tests for the alerts source."""
from homeassistant.components.news.const import NewsSource
from homeassistant.components.news.manager import NewsManager
from homeassistant.components.news.source_alerts import SOURCE_URL, source_update_alerts


async def test_source_update_alerts(hass, aioclient_mock):
    """Test source_update_alerts."""
    aioclient_mock.get(
        SOURCE_URL,
        json=[
            {
                "title": "Test alert",
                "created": "1970-01-01T00:00:00.000Z",
                "integrations": [{"package": "awesome"}],
                "homeassistant": {"package": "homeassistant", "min": "1.2.3"},
                "alert_url": "https://alerts.home-assistant.io/#test.markdown",
            },
            {
                "title": "Test alert 2",
                "created": "1970-01-02T00:00:00.000Z",
                "integrations": [{"package": "not_awesome"}],
                "homeassistant": {"package": "homeassistant", "min": "1.2.3"},
                "alert_url": "https://alerts.home-assistant.io/#test2.markdown",
            },
        ],
    )
    manager = NewsManager(hass)
    await manager.load()
    assert len(manager.events) == 0

    hass.config.components.add("awesome")
    manager._data["active"] = {"alerts.old": {"source": NewsSource.ALERTS}}
    assert len(manager.events) == 1
    await source_update_alerts(hass, manager)
    assert len(manager.events) == 1
    assert "alerts.old" not in manager.events
    assert (
        manager.events["alerts.1970_01_01t00_00_00_000z"]["url"]
        == "https://alerts.home-assistant.io/#test.markdown"
    )
