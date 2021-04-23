"""The tests for the analytics ."""
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import aiohttp
import pytest

from homeassistant.components.analytics.analytics import Analytics
from homeassistant.components.analytics.const import (
    ANALYTICS_ENDPOINT_URL,
    ANALYTICS_ENDPOINT_URL_DEV,
    ATTR_BASE,
    ATTR_DIAGNOSTICS,
    ATTR_PREFERENCES,
    ATTR_STATISTICS,
    ATTR_USAGE,
)
from homeassistant.components.api import ATTR_UUID
from homeassistant.const import ATTR_DOMAIN
from homeassistant.loader import IntegrationNotFound
from homeassistant.setup import async_setup_component

MOCK_UUID = "abcdefg"
MOCK_VERSION = "1970.1.0"
MOCK_VERSION_DEV = "1970.1.0.dev0"
MOCK_VERSION_NIGHTLY = "1970.1.0.dev19700101"


async def test_no_send(hass, caplog, aioclient_mock):
    """Test send when no prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    with patch(
        "homeassistant.components.hassio.is_hassio",
        side_effect=Mock(return_value=False),
    ):
        assert not analytics.preferences[ATTR_BASE]

        await analytics.send_analytics()

    assert "Nothing to submit" in caplog.text
    assert len(aioclient_mock.mock_calls) == 0


async def test_load_with_supervisor_diagnostics(hass):
    """Test loading with a supervisor that has diagnostics enabled."""
    analytics = Analytics(hass)
    assert not analytics.preferences[ATTR_DIAGNOSTICS]
    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(return_value={"diagnostics": True}),
    ), patch(
        "homeassistant.components.hassio.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        await analytics.load()
    assert analytics.preferences[ATTR_DIAGNOSTICS]


async def test_load_with_supervisor_without_diagnostics(hass):
    """Test loading with a supervisor that has not diagnostics enabled."""
    analytics = Analytics(hass)
    analytics._data[ATTR_PREFERENCES][ATTR_DIAGNOSTICS] = True

    assert analytics.preferences[ATTR_DIAGNOSTICS]

    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(return_value={"diagnostics": False}),
    ), patch(
        "homeassistant.components.hassio.is_hassio",
        side_effect=Mock(return_value=True),
    ):
        await analytics.load()

    assert not analytics.preferences[ATTR_DIAGNOSTICS]


async def test_failed_to_send(hass, caplog, aioclient_mock):
    """Test failed to send payload."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=400)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()
    assert (
        f"Sending analytics failed with statuscode 400 from {ANALYTICS_ENDPOINT_URL_DEV}"
        in caplog.text
    )


async def test_failed_to_send_raises(hass, caplog, aioclient_mock):
    """Test raises when failed to send payload."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, exc=aiohttp.ClientError())
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()
    assert "Error sending analytics" in caplog.text


async def test_send_base(hass, caplog, aioclient_mock):
    """Test send base prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)

    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    with patch("uuid.UUID.hex", new_callable=PropertyMock) as hex, patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        hex.return_value = MOCK_UUID
        await analytics.send_analytics()

    assert f"'uuid': '{MOCK_UUID}'" in caplog.text
    assert f"'version': '{MOCK_VERSION_DEV}'" in caplog.text
    assert "'installation_type':" in caplog.text
    assert "'integration_count':" not in caplog.text
    assert "'integrations':" not in caplog.text


async def test_send_base_with_supervisor(hass, caplog, aioclient_mock):
    """Test send base prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)

    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})
    assert analytics.preferences[ATTR_BASE]

    with patch(
        "homeassistant.components.hassio.get_supervisor_info",
        side_effect=Mock(return_value={"supported": True, "healthy": True}),
    ), patch(
        "homeassistant.components.hassio.get_info",
        side_effect=Mock(return_value={}),
    ), patch(
        "homeassistant.components.hassio.get_host_info",
        side_effect=Mock(return_value={}),
    ), patch(
        "homeassistant.components.hassio.is_hassio",
        side_effect=Mock(return_value=True),
    ), patch(
        "uuid.UUID.hex", new_callable=PropertyMock
    ) as hex, patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        hex.return_value = MOCK_UUID
        await analytics.load()

        await analytics.send_analytics()

    assert f"'uuid': '{MOCK_UUID}'" in caplog.text
    assert f"'version': '{MOCK_VERSION_DEV}'" in caplog.text
    assert "'supervisor': {'healthy': True, 'supported': True}}" in caplog.text
    assert "'installation_type':" in caplog.text
    assert "'integration_count':" not in caplog.text
    assert "'integrations':" not in caplog.text


async def test_send_usage(hass, caplog, aioclient_mock):
    """Test send usage prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})

    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_USAGE]
    hass.config.components = ["default_config"]

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()

    assert "'integrations': ['default_config']" in caplog.text
    assert "'integration_count':" not in caplog.text


async def test_send_usage_with_supervisor(hass, caplog, aioclient_mock):
    """Test send usage with supervisor prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)

    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_USAGE]
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
        "homeassistant.components.hassio.get_info",
        side_effect=Mock(return_value={}),
    ), patch(
        "homeassistant.components.hassio.get_host_info",
        side_effect=Mock(return_value={}),
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
        "homeassistant.components.hassio.is_hassio",
        side_effect=Mock(return_value=True),
    ), patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()
    assert (
        "'addons': [{'slug': 'test_addon', 'protected': True, 'version': '1', 'auto_update': False}]"
        in caplog.text
    )
    assert "'addon_count':" not in caplog.text


async def test_send_statistics(hass, caplog, aioclient_mock):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components = ["default_config"]

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()
    assert (
        "'state_count': 0, 'automation_count': 0, 'integration_count': 1, 'user_count': 0"
        in caplog.text
    )
    assert "'integrations':" not in caplog.text


async def test_send_statistics_one_integration_fails(hass, caplog, aioclient_mock):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components = ["default_config"]

    with patch(
        "homeassistant.components.analytics.analytics.async_get_integration",
        side_effect=IntegrationNotFound("any"),
    ), patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()

    post_call = aioclient_mock.mock_calls[0]
    assert "uuid" in post_call[2]
    assert post_call[2]["integration_count"] == 0


async def test_send_statistics_async_get_integration_unknown_exception(
    hass, caplog, aioclient_mock
):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]
    hass.config.components = ["default_config"]

    with pytest.raises(ValueError), patch(
        "homeassistant.components.analytics.analytics.async_get_integration",
        side_effect=ValueError,
    ):
        await analytics.send_analytics()


async def test_send_statistics_with_supervisor(hass, caplog, aioclient_mock):
    """Test send statistics prefrences are defined."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True, ATTR_STATISTICS: True})
    assert analytics.preferences[ATTR_BASE]
    assert analytics.preferences[ATTR_STATISTICS]

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
        "homeassistant.components.hassio.get_info",
        side_effect=Mock(return_value={}),
    ), patch(
        "homeassistant.components.hassio.get_host_info",
        side_effect=Mock(return_value={}),
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
        "homeassistant.components.hassio.is_hassio",
        side_effect=Mock(return_value=True),
    ), patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()
    assert "'addon_count': 1" in caplog.text
    assert "'integrations':" not in caplog.text


async def test_reusing_uuid(hass, aioclient_mock):
    """Test reusing the stored UUID."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    analytics._data[ATTR_UUID] = "NOT_MOCK_UUID"

    await analytics.save_preferences({ATTR_BASE: True})

    with patch("uuid.UUID.hex", new_callable=PropertyMock) as hex, patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        # This is not actually called but that in itself prove the test
        hex.return_value = MOCK_UUID
        await analytics.send_analytics()

    assert analytics.uuid == "NOT_MOCK_UUID"


async def test_custom_integrations(hass, aioclient_mock):
    """Test sending custom integrations."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL_DEV, status=200)
    analytics = Analytics(hass)
    assert await async_setup_component(hass, "test_package", {"test_package": {}})
    await analytics.save_preferences({ATTR_BASE: True, ATTR_USAGE: True})

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_DEV
    ):
        await analytics.send_analytics()

    payload = aioclient_mock.mock_calls[0][2]
    assert payload["custom_integrations"][0][ATTR_DOMAIN] == "test_package"


async def test_production_url(hass, aioclient_mock):
    """Test sending payload to production url."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})

    with patch("homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION):
        await analytics.send_analytics()

    payload = aioclient_mock.mock_calls[0]
    assert str(payload[1]) == ANALYTICS_ENDPOINT_URL


async def test_production_url_error(hass, aioclient_mock, caplog):
    """Test sending payload to production url that returns error."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=400)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})

    with patch("homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION):

        await analytics.send_analytics()

    payload = aioclient_mock.mock_calls[0]
    assert str(payload[1]) == ANALYTICS_ENDPOINT_URL
    assert (
        f"Sending analytics failed with statuscode 400 from {ANALYTICS_ENDPOINT_URL}"
        in caplog.text
    )


async def test_nightly_endpoint(hass, aioclient_mock):
    """Test sending payload to production url when running nightly."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    analytics = Analytics(hass)
    await analytics.save_preferences({ATTR_BASE: True})

    with patch(
        "homeassistant.components.analytics.analytics.HA_VERSION", MOCK_VERSION_NIGHTLY
    ):

        await analytics.send_analytics()

    payload = aioclient_mock.mock_calls[0]
    assert str(payload[1]) == ANALYTICS_ENDPOINT_URL
