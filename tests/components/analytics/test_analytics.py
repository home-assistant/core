"""The tests for the analytics ."""
from homeassistant.components.analytics.analytics import Analytics
from homeassistant.components.analytics.const import (
    ANALYTICS_ENDPOINT_URL,
    AnalyticsPreference,
)
from homeassistant.components.hassio.const import DOMAIN as HASSIO_DOMAIN
from homeassistant.const import __version__ as HA_VERSION

MOCK_HUUID = "abcdefg"


async def test_no_send(hass, caplog, aioclient_mock):
    """Test send when no prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.load()
    assert analytics.preferences == []

    await analytics.send_analytics()
    assert "Nothing to submit" in caplog.text
    assert len(aioclient_mock.mock_calls) == 0


async def test_failed_to_send(hass, caplog, aioclient_mock):
    """Test send base prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=400)
    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.save_preferences([AnalyticsPreference.BASE])
    assert analytics.preferences == ["base"]

    await analytics.send_analytics()
    assert "Sending analytics failed with statuscode 400" in caplog.text


async def test_send_base(hass, caplog, aioclient_mock):
    """Test send base prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.save_preferences([AnalyticsPreference.BASE])
    assert analytics.preferences == ["base"]

    await analytics.send_analytics()
    assert f"'huuid': '{MOCK_HUUID}'" in caplog.text
    assert f"'version': '{HA_VERSION}'" in caplog.text
    assert "'installation_type':" in caplog.text
    assert "'integration_count':" not in caplog.text
    assert "'integrations':" not in caplog.text


async def test_send_base_with_supervisor(hass, caplog, aioclient_mock, hassio_handler):
    """Test send base prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={"result": "ok", "data": {"supported": True, "healthy": True}},
    )
    hass.data[HASSIO_DOMAIN] = hassio_handler

    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.save_preferences([AnalyticsPreference.BASE])
    assert analytics.preferences == ["base"]

    await analytics.send_analytics()
    assert f"'huuid': '{MOCK_HUUID}'" in caplog.text
    assert f"'version': '{HA_VERSION}'" in caplog.text
    assert "'supervisor': {'healthy': True, 'supported': True}}" in caplog.text
    assert "'installation_type':" in caplog.text
    assert "'integration_count':" not in caplog.text
    assert "'integrations':" not in caplog.text


async def test_send_usage(hass, caplog, aioclient_mock):
    """Test send usage prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.USAGE]
    )
    assert analytics.preferences == ["base", "usage"]
    hass.config.components = ["default_config"]

    await analytics.send_analytics()
    assert "'integrations': ['default_config']" in caplog.text
    assert "'integration_count':" not in caplog.text


async def test_send_usage_with_supervisor(hass, caplog, aioclient_mock, hassio_handler):
    """Test send usage with supervisor prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "healthy": True,
                "supported": True,
                "addons": [{"slug": "test_addon"}],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/addons/test_addon/info",
        json={
            "result": "ok",
            "data": {
                "slug": "test_addon",
                "protected": True,
                "version": "1",
                "auto_update": False,
            },
        },
    )
    hass.data[HASSIO_DOMAIN] = hassio_handler

    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.USAGE]
    )
    assert analytics.preferences == ["base", "usage"]
    hass.config.components = ["default_config"]

    await analytics.send_analytics()
    assert (
        "'addons': [{'slug': 'test_addon', 'protected': True, 'version': '1', 'auto_update': False}]"
        in caplog.text
    )
    assert "'addon_count':" not in caplog.text


async def test_send_statistics(hass, caplog, aioclient_mock):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.STATISTICS]
    )
    assert analytics.preferences == ["base", "statistics"]
    hass.config.components = ["default_config"]

    await analytics.send_analytics()
    assert (
        "'state_count': 0, 'automation_count': 0, 'integration_count': 1, 'user_count': 0"
        in caplog.text
    )
    assert "'integrations':" not in caplog.text


async def test_send_statistics_with_supervisor(
    hass, caplog, aioclient_mock, hassio_handler
):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "healthy": True,
                "supported": True,
                "addons": [{"slug": "test_addon"}],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/addons/test_addon/info",
        json={
            "result": "ok",
            "data": {
                "slug": "test_addon",
                "protected": True,
                "version": "1",
                "auto_update": False,
            },
        },
    )
    hass.data[HASSIO_DOMAIN] = hassio_handler

    analytics = Analytics(hass, MOCK_HUUID)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.STATISTICS]
    )
    assert analytics.preferences == ["base", "statistics"]

    await analytics.send_analytics()
    assert "'addon_count': 1" in caplog.text
    assert "'integrations':" not in caplog.text
