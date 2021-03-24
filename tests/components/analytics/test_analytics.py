"""The tests for the analytics ."""
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import aiohttp

from homeassistant.components.analytics.analytics import Analytics
from homeassistant.components.analytics.const import (
    ANALYTICS_ENDPOINT_URL,
    ATTR_PREFERENCES,
    AnalyticsPreference,
)
from homeassistant.const import __version__ as HA_VERSION

MOCK_HUUID = "abcdefg"


async def test_no_send(hass, caplog, aioclient_mock):
    """Test send when no prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.load()
    assert analytics.preferences == []

    with patch("homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID):
        await analytics.send_analytics()
    assert "Nothing to submit" in caplog.text
    assert len(aioclient_mock.mock_calls) == 0


async def test_load_with_supervisor_diagnostics(hass):
    """Test loading with a supervisor that has diagnostics enabled."""
    analytics = Analytics(hass)
    assert AnalyticsPreference.DIAGNOSTICS not in analytics.preferences
    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(return_value={"diagnostics": True}),
    ), patch(
        "homeassistant.components.analytics.analytics.Analytics.supervisor",
        PropertyMock(return_value=True),
    ):
        await analytics.load()
    assert AnalyticsPreference.DIAGNOSTICS in analytics.preferences


async def test_load_with_supervisor_without_diagnostics(hass):
    """Test loading with a supervisor that has not diagnostics enabled."""
    analytics = Analytics(hass)
    analytics._data[ATTR_PREFERENCES] = [AnalyticsPreference.DIAGNOSTICS]

    assert AnalyticsPreference.DIAGNOSTICS in analytics.preferences

    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(return_value={"diagnostics": False}),
    ), patch(
        "homeassistant.components.analytics.analytics.Analytics.supervisor",
        PropertyMock(return_value=True),
    ):
        await analytics.load()

    assert AnalyticsPreference.DIAGNOSTICS not in analytics.preferences


async def test_failed_to_send(hass, caplog, aioclient_mock):
    """Test failed to send payload."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=400)
    analytics = Analytics(hass)
    await analytics.save_preferences([AnalyticsPreference.BASE])
    assert analytics.preferences == ["base"]

    with patch("homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID):
        await analytics.send_analytics()
    assert "Sending analytics failed with statuscode 400" in caplog.text


async def test_failed_to_send_raises(hass, caplog, aioclient_mock):
    """Test raises when failed to send payload."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, exc=aiohttp.ClientError())
    analytics = Analytics(hass)
    await analytics.save_preferences([AnalyticsPreference.BASE])
    assert analytics.preferences == ["base"]

    with patch("homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID):
        await analytics.send_analytics()
    assert "Error sending analytics" in caplog.text


async def test_send_base(hass, caplog, aioclient_mock):
    """Test send base prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences([AnalyticsPreference.BASE])
    assert analytics.preferences == ["base"]

    with patch("homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID):
        await analytics.send_analytics()
    assert f"'huuid': '{MOCK_HUUID}'" in caplog.text
    assert f"'version': '{HA_VERSION}'" in caplog.text
    assert "'installation_type':" in caplog.text
    assert "'integration_count':" not in caplog.text
    assert "'integrations':" not in caplog.text


async def test_send_base_with_supervisor(hass, caplog, aioclient_mock):
    """Test send base prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)

    analytics = Analytics(hass)
    await analytics.save_preferences([AnalyticsPreference.BASE])
    assert analytics.preferences == ["base"]

    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(return_value={"supported": True, "healthy": True}),
    ), patch(
        "homeassistant.components.analytics.analytics.Analytics.supervisor",
        PropertyMock(return_value=True),
    ), patch(
        "homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID
    ):
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
    analytics = Analytics(hass)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.USAGE]
    )
    assert analytics.preferences == ["base", "usage"]
    hass.config.components = ["default_config", "api"]

    with patch("homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID):
        await analytics.send_analytics()
    assert "'integrations': ['default_config']" in caplog.text
    assert "'integration_count':" not in caplog.text


async def test_send_usage_with_supervisor(hass, caplog, aioclient_mock):
    """Test send usage with supervisor prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)

    analytics = Analytics(hass)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.USAGE]
    )
    assert analytics.preferences == ["base", "usage"]
    hass.config.components = ["default_config"]

    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(
            return_value={
                "healthy": True,
                "supported": True,
                "addons": [{"slug": "test_addon"}],
            }
        ),
    ), patch(
        "homeassistant.components.hassio.async_get_addon_info",
        side_effect=AsyncMock(
            return_value={
                "slug": "test_addon",
                "protected": True,
                "version": "1",
                "auto_update": False,
            }
        ),
    ), patch(
        "homeassistant.components.analytics.analytics.Analytics.supervisor",
        PropertyMock(return_value=True),
    ), patch(
        "homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID
    ):
        await analytics.send_analytics()
    assert (
        "'addons': [{'slug': 'test_addon', 'protected': True, 'version': '1', 'auto_update': False}]"
        in caplog.text
    )
    assert "'addon_count':" not in caplog.text


async def test_send_statistics(hass, caplog, aioclient_mock):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.STATISTICS]
    )
    assert analytics.preferences == ["base", "statistics"]
    hass.config.components = ["default_config"]

    with patch("homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID):
        await analytics.send_analytics()
    assert (
        "'state_count': 0, 'automation_count': 0, 'integration_count': 1, 'user_count': 0"
        in caplog.text
    )
    assert "'integrations':" not in caplog.text


async def test_send_statistics_with_supervisor(hass, caplog, aioclient_mock):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences(
        [AnalyticsPreference.BASE, AnalyticsPreference.STATISTICS]
    )
    assert analytics.preferences == ["base", "statistics"]

    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(
            return_value={
                "healthy": True,
                "supported": True,
                "addons": [{"slug": "test_addon"}],
            }
        ),
    ), patch(
        "homeassistant.components.hassio.async_get_addon_info",
        side_effect=AsyncMock(
            return_value={
                "slug": "test_addon",
                "protected": True,
                "version": "1",
                "auto_update": False,
            }
        ),
    ), patch(
        "homeassistant.components.analytics.analytics.Analytics.supervisor",
        PropertyMock(return_value=True),
    ), patch(
        "homeassistant.helpers.instance_id.async_get", return_value=MOCK_HUUID
    ):
        await analytics.send_analytics()
    assert "'addon_count': 1" in caplog.text
    assert "'integrations':" not in caplog.text
