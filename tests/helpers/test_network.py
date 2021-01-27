"""Test network helper."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import cloud
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import (
    NoURLAvailableError,
    _get_cloud_url,
    _get_deprecated_base_url,
    _get_external_url,
    _get_internal_url,
    _get_request_host,
    get_url,
    is_internal_request,
)

from tests.common import mock_component


async def test_get_url_internal(hass: HomeAssistant):
    """Test getting an instance URL when the user has set an internal URL."""
    assert hass.config.internal_url is None

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_current_request=True)

    # Test with internal URL: http://example.local:8123
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    assert hass.config.internal_url == "http://example.local:8123"
    assert _get_internal_url(hass) == "http://example.local:8123"
    assert _get_internal_url(hass, allow_ip=False) == "http://example.local:8123"

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_current_request=True)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="example.local"
    ):
        assert (
            _get_internal_url(hass, require_current_request=True)
            == "http://example.local:8123"
        )

        with pytest.raises(NoURLAvailableError):
            _get_internal_url(
                hass, require_current_request=True, require_standard_port=True
            )

        with pytest.raises(NoURLAvailableError):
            _get_internal_url(hass, require_current_request=True, require_ssl=True)

    with patch(
        "homeassistant.helpers.network._get_request_host",
        return_value="no_match.example.local",
    ), pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_current_request=True)

    # Test with internal URL: https://example.local:8123
    await async_process_ha_core_config(
        hass,
        {"internal_url": "https://example.local:8123"},
    )

    assert hass.config.internal_url == "https://example.local:8123"
    assert _get_internal_url(hass) == "https://example.local:8123"
    assert _get_internal_url(hass, allow_ip=False) == "https://example.local:8123"
    assert _get_internal_url(hass, require_ssl=True) == "https://example.local:8123"

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_standard_port=True)

    # Test with internal URL: http://example.local:80/
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:80/"},
    )

    assert hass.config.internal_url == "http://example.local:80/"
    assert _get_internal_url(hass) == "http://example.local"
    assert _get_internal_url(hass, allow_ip=False) == "http://example.local"
    assert _get_internal_url(hass, require_standard_port=True) == "http://example.local"

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)

    # Test with internal URL: https://example.local:443
    await async_process_ha_core_config(
        hass,
        {"internal_url": "https://example.local:443"},
    )

    assert hass.config.internal_url == "https://example.local:443"
    assert _get_internal_url(hass) == "https://example.local"
    assert _get_internal_url(hass, allow_ip=False) == "https://example.local"
    assert (
        _get_internal_url(hass, require_standard_port=True) == "https://example.local"
    )
    assert _get_internal_url(hass, require_ssl=True) == "https://example.local"

    # Test with internal URL: https://192.168.0.1
    await async_process_ha_core_config(
        hass,
        {"internal_url": "https://192.168.0.1"},
    )

    assert hass.config.internal_url == "https://192.168.0.1"
    assert _get_internal_url(hass) == "https://192.168.0.1"
    assert _get_internal_url(hass, require_standard_port=True) == "https://192.168.0.1"
    assert _get_internal_url(hass, require_ssl=True) == "https://192.168.0.1"

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, allow_ip=False)

    # Test with internal URL: http://192.168.0.1:8123
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://192.168.0.1:8123"},
    )

    assert hass.config.internal_url == "http://192.168.0.1:8123"
    assert _get_internal_url(hass) == "http://192.168.0.1:8123"

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, allow_ip=False)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="192.168.0.1"
    ):
        assert (
            _get_internal_url(hass, require_current_request=True)
            == "http://192.168.0.1:8123"
        )

        with pytest.raises(NoURLAvailableError):
            _get_internal_url(hass, require_current_request=True, allow_ip=False)

        with pytest.raises(NoURLAvailableError):
            _get_internal_url(
                hass, require_current_request=True, require_standard_port=True
            )

        with pytest.raises(NoURLAvailableError):
            _get_internal_url(hass, require_current_request=True, require_ssl=True)


async def test_get_url_internal_fallback(hass: HomeAssistant):
    """Test getting an instance URL when the user has not set an internal URL."""
    assert hass.config.internal_url is None

    hass.config.api = Mock(
        use_ssl=False, port=8123, deprecated_base_url=None, local_ip="192.168.123.123"
    )
    assert _get_internal_url(hass) == "http://192.168.123.123:8123"

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)

    hass.config.api = Mock(
        use_ssl=False, port=80, deprecated_base_url=None, local_ip="192.168.123.123"
    )
    assert _get_internal_url(hass) == "http://192.168.123.123"
    assert (
        _get_internal_url(hass, require_standard_port=True) == "http://192.168.123.123"
    )

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)

    hass.config.api = Mock(use_ssl=True, port=443, deprecated_base_url=None)
    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)

    # Do no accept any local loopback address as fallback
    hass.config.api = Mock(
        use_ssl=False, port=80, deprecated_base_url=None, local_ip="127.0.0.1"
    )
    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)


async def test_get_url_external(hass: HomeAssistant):
    """Test getting an instance URL when the user has set an external URL."""
    assert hass.config.external_url is None

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_current_request=True)

    # Test with external URL: http://example.com:8123
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com:8123"},
    )

    assert hass.config.external_url == "http://example.com:8123"
    assert _get_external_url(hass) == "http://example.com:8123"
    assert _get_external_url(hass, allow_cloud=False) == "http://example.com:8123"
    assert _get_external_url(hass, allow_ip=False) == "http://example.com:8123"
    assert _get_external_url(hass, prefer_cloud=True) == "http://example.com:8123"

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_current_request=True)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="example.com"
    ):
        assert (
            _get_external_url(hass, require_current_request=True)
            == "http://example.com:8123"
        )

        with pytest.raises(NoURLAvailableError):
            _get_external_url(
                hass, require_current_request=True, require_standard_port=True
            )

        with pytest.raises(NoURLAvailableError):
            _get_external_url(hass, require_current_request=True, require_ssl=True)

    with patch(
        "homeassistant.helpers.network._get_request_host",
        return_value="no_match.example.com",
    ), pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_current_request=True)

    # Test with external URL: http://example.com:80/
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com:80/"},
    )

    assert hass.config.external_url == "http://example.com:80/"
    assert _get_external_url(hass) == "http://example.com"
    assert _get_external_url(hass, allow_cloud=False) == "http://example.com"
    assert _get_external_url(hass, allow_ip=False) == "http://example.com"
    assert _get_external_url(hass, prefer_cloud=True) == "http://example.com"
    assert _get_external_url(hass, require_standard_port=True) == "http://example.com"

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_ssl=True)

    # Test with external url: https://example.com:443/
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com:443/"},
    )
    assert hass.config.external_url == "https://example.com:443/"
    assert _get_external_url(hass) == "https://example.com"
    assert _get_external_url(hass, allow_cloud=False) == "https://example.com"
    assert _get_external_url(hass, allow_ip=False) == "https://example.com"
    assert _get_external_url(hass, prefer_cloud=True) == "https://example.com"
    assert _get_external_url(hass, require_ssl=False) == "https://example.com"
    assert _get_external_url(hass, require_standard_port=True) == "https://example.com"

    # Test with external URL: https://example.com:80
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com:80"},
    )
    assert hass.config.external_url == "https://example.com:80"
    assert _get_external_url(hass) == "https://example.com:80"
    assert _get_external_url(hass, allow_cloud=False) == "https://example.com:80"
    assert _get_external_url(hass, allow_ip=False) == "https://example.com:80"
    assert _get_external_url(hass, prefer_cloud=True) == "https://example.com:80"
    assert _get_external_url(hass, require_ssl=True) == "https://example.com:80"

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_standard_port=True)

    # Test with external URL: https://192.168.0.1
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://192.168.0.1"},
    )
    assert hass.config.external_url == "https://192.168.0.1"
    assert _get_external_url(hass) == "https://192.168.0.1"
    assert _get_external_url(hass, allow_cloud=False) == "https://192.168.0.1"
    assert _get_external_url(hass, prefer_cloud=True) == "https://192.168.0.1"
    assert _get_external_url(hass, require_standard_port=True) == "https://192.168.0.1"

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass, require_ssl=True)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="192.168.0.1"
    ):
        assert (
            _get_external_url(hass, require_current_request=True)
            == "https://192.168.0.1"
        )

        with pytest.raises(NoURLAvailableError):
            _get_external_url(hass, require_current_request=True, allow_ip=False)

        with pytest.raises(NoURLAvailableError):
            _get_external_url(hass, require_current_request=True, require_ssl=True)


async def test_get_cloud_url(hass: HomeAssistant):
    """Test getting an instance URL when the user has set an external URL."""
    assert hass.config.external_url is None
    hass.config.components.add("cloud")

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert _get_cloud_url(hass) == "https://example.nabu.casa"

        with pytest.raises(NoURLAvailableError):
            _get_cloud_url(hass, require_current_request=True)

        with patch(
            "homeassistant.helpers.network._get_request_host",
            return_value="example.nabu.casa",
        ):
            assert (
                _get_cloud_url(hass, require_current_request=True)
                == "https://example.nabu.casa"
            )

        with patch(
            "homeassistant.helpers.network._get_request_host",
            return_value="no_match.nabu.casa",
        ), pytest.raises(NoURLAvailableError):
            _get_cloud_url(hass, require_current_request=True)

    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        side_effect=cloud.CloudNotAvailable,
    ):
        with pytest.raises(NoURLAvailableError):
            _get_cloud_url(hass)


async def test_get_external_url_cloud_fallback(hass: HomeAssistant):
    """Test getting an external instance URL with cloud fallback."""
    assert hass.config.external_url is None

    # Test with external URL: http://1.1.1.1:8123
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://1.1.1.1:8123"},
    )

    assert hass.config.external_url == "http://1.1.1.1:8123"
    assert _get_external_url(hass, prefer_cloud=True) == "http://1.1.1.1:8123"

    # Add Cloud to the previous test
    hass.config.components.add("cloud")
    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert _get_external_url(hass, allow_cloud=False) == "http://1.1.1.1:8123"
        assert _get_external_url(hass, allow_ip=False) == "https://example.nabu.casa"
        assert _get_external_url(hass, prefer_cloud=False) == "http://1.1.1.1:8123"
        assert _get_external_url(hass, prefer_cloud=True) == "https://example.nabu.casa"
        assert _get_external_url(hass, require_ssl=True) == "https://example.nabu.casa"
        assert (
            _get_external_url(hass, require_standard_port=True)
            == "https://example.nabu.casa"
        )

    # Test with external URL: https://example.com
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )

    assert hass.config.external_url == "https://example.com"
    assert _get_external_url(hass, prefer_cloud=True) == "https://example.com"

    # Add Cloud to the previous test
    hass.config.components.add("cloud")
    with patch.object(
        hass.components.cloud,
        "async_remote_ui_url",
        return_value="https://example.nabu.casa",
    ):
        assert _get_external_url(hass, allow_cloud=False) == "https://example.com"
        assert _get_external_url(hass, allow_ip=False) == "https://example.com"
        assert _get_external_url(hass, prefer_cloud=False) == "https://example.com"
        assert _get_external_url(hass, prefer_cloud=True) == "https://example.nabu.casa"
        assert _get_external_url(hass, require_ssl=True) == "https://example.com"
        assert (
            _get_external_url(hass, require_standard_port=True) == "https://example.com"
        )
        assert (
            _get_external_url(hass, prefer_cloud=True, allow_cloud=False)
            == "https://example.com"
        )


async def test_get_url(hass: HomeAssistant):
    """Test getting an instance URL."""
    assert hass.config.external_url is None
    assert hass.config.internal_url is None

    with pytest.raises(NoURLAvailableError):
        get_url(hass)

    hass.config.api = Mock(
        use_ssl=False, port=8123, deprecated_base_url=None, local_ip="192.168.123.123"
    )
    assert get_url(hass) == "http://192.168.123.123:8123"
    assert get_url(hass, prefer_external=True) == "http://192.168.123.123:8123"

    with pytest.raises(NoURLAvailableError):
        get_url(hass, allow_internal=False)

    # Test only external
    hass.config.api = None
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )
    assert hass.config.external_url == "https://example.com"
    assert hass.config.internal_url is None
    assert get_url(hass) == "https://example.com"

    # Test preference or allowance
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local", "external_url": "https://example.com"},
    )
    assert hass.config.external_url == "https://example.com"
    assert hass.config.internal_url == "http://example.local"
    assert get_url(hass) == "http://example.local"
    assert get_url(hass, prefer_external=True) == "https://example.com"
    assert get_url(hass, allow_internal=False) == "https://example.com"
    assert (
        get_url(hass, prefer_external=True, allow_external=False)
        == "http://example.local"
    )

    with pytest.raises(NoURLAvailableError):
        get_url(hass, allow_external=False, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        get_url(hass, allow_external=False, allow_internal=False)

    with pytest.raises(NoURLAvailableError):
        get_url(hass, require_current_request=True)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="example.com"
    ), patch("homeassistant.components.http.current_request"):
        assert get_url(hass, require_current_request=True) == "https://example.com"
        assert (
            get_url(hass, require_current_request=True, require_ssl=True)
            == "https://example.com"
        )

        with pytest.raises(NoURLAvailableError):
            get_url(hass, require_current_request=True, allow_external=False)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="example.local"
    ), patch("homeassistant.components.http.current_request"):
        assert get_url(hass, require_current_request=True) == "http://example.local"

        with pytest.raises(NoURLAvailableError):
            get_url(hass, require_current_request=True, allow_internal=False)

        with pytest.raises(NoURLAvailableError):
            get_url(hass, require_current_request=True, require_ssl=True)

    with patch(
        "homeassistant.helpers.network._get_request_host",
        return_value="no_match.example.com",
    ), pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_current_request=True)


async def test_get_request_host(hass: HomeAssistant):
    """Test getting the host of the current web request from the request context."""
    with pytest.raises(NoURLAvailableError):
        _get_request_host()

    with patch("homeassistant.components.http.current_request") as mock_request_context:
        mock_request = Mock()
        mock_request.url = "http://example.com:8123/test/request"
        mock_request_context.get = Mock(return_value=mock_request)

        assert _get_request_host() == "example.com"


async def test_get_deprecated_base_url_internal(hass: HomeAssistant):
    """Test getting an internal instance URL from the deprecated base_url."""
    # Test with SSL local URL
    hass.config.api = Mock(deprecated_base_url="https://example.local")
    assert _get_deprecated_base_url(hass, internal=True) == "https://example.local"
    assert (
        _get_deprecated_base_url(hass, internal=True, allow_ip=False)
        == "https://example.local"
    )
    assert (
        _get_deprecated_base_url(hass, internal=True, require_ssl=True)
        == "https://example.local"
    )
    assert (
        _get_deprecated_base_url(hass, internal=True, require_standard_port=True)
        == "https://example.local"
    )

    # Test with no SSL, local IP URL
    hass.config.api = Mock(deprecated_base_url="http://10.10.10.10:8123")
    assert _get_deprecated_base_url(hass, internal=True) == "http://10.10.10.10:8123"

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, require_standard_port=True)

    # Test with SSL, local IP URL
    hass.config.api = Mock(deprecated_base_url="https://10.10.10.10")
    assert _get_deprecated_base_url(hass, internal=True) == "https://10.10.10.10"
    assert (
        _get_deprecated_base_url(hass, internal=True, require_ssl=True)
        == "https://10.10.10.10"
    )
    assert (
        _get_deprecated_base_url(hass, internal=True, require_standard_port=True)
        == "https://10.10.10.10"
    )

    # Test external URL
    hass.config.api = Mock(deprecated_base_url="https://example.com")
    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, allow_ip=False)

    # Test with loopback
    hass.config.api = Mock(deprecated_base_url="https://127.0.0.42")
    with pytest.raises(NoURLAvailableError):
        assert _get_deprecated_base_url(hass, internal=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, internal=True, require_standard_port=True)


async def test_get_deprecated_base_url_external(hass: HomeAssistant):
    """Test getting an external instance URL from the deprecated base_url."""
    # Test with SSL and external domain on standard port
    hass.config.api = Mock(deprecated_base_url="https://example.com:443/")
    assert _get_deprecated_base_url(hass) == "https://example.com"
    assert _get_deprecated_base_url(hass, require_ssl=True) == "https://example.com"
    assert (
        _get_deprecated_base_url(hass, require_standard_port=True)
        == "https://example.com"
    )

    # Test without SSL and external domain on non-standard port
    hass.config.api = Mock(deprecated_base_url="http://example.com:8123/")
    assert _get_deprecated_base_url(hass) == "http://example.com:8123"

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_standard_port=True)

    # Test SSL on external IP
    hass.config.api = Mock(deprecated_base_url="https://1.1.1.1")
    assert _get_deprecated_base_url(hass) == "https://1.1.1.1"
    assert _get_deprecated_base_url(hass, require_ssl=True) == "https://1.1.1.1"
    assert (
        _get_deprecated_base_url(hass, require_standard_port=True) == "https://1.1.1.1"
    )

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, allow_ip=False)

    # Test with private IP
    hass.config.api = Mock(deprecated_base_url="https://10.10.10.10")
    with pytest.raises(NoURLAvailableError):
        assert _get_deprecated_base_url(hass)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_standard_port=True)

    # Test with local domain
    hass.config.api = Mock(deprecated_base_url="https://example.local")
    with pytest.raises(NoURLAvailableError):
        assert _get_deprecated_base_url(hass)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_standard_port=True)

    # Test with loopback
    hass.config.api = Mock(deprecated_base_url="https://127.0.0.42")
    with pytest.raises(NoURLAvailableError):
        assert _get_deprecated_base_url(hass)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_ssl=True)

    with pytest.raises(NoURLAvailableError):
        _get_deprecated_base_url(hass, require_standard_port=True)


async def test_get_internal_url_with_base_url_fallback(hass: HomeAssistant):
    """Test getting an internal instance URL with the deprecated base_url fallback."""
    hass.config.api = Mock(
        use_ssl=False, port=8123, deprecated_base_url=None, local_ip="192.168.123.123"
    )
    assert hass.config.internal_url is None
    assert _get_internal_url(hass) == "http://192.168.123.123:8123"

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, allow_ip=False)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_standard_port=True)

    with pytest.raises(NoURLAvailableError):
        _get_internal_url(hass, require_ssl=True)

    # Add base_url
    hass.config.api = Mock(
        use_ssl=False, port=8123, deprecated_base_url="https://example.local"
    )
    assert _get_internal_url(hass) == "https://example.local"
    assert _get_internal_url(hass, allow_ip=False) == "https://example.local"
    assert (
        _get_internal_url(hass, require_standard_port=True) == "https://example.local"
    )
    assert _get_internal_url(hass, require_ssl=True) == "https://example.local"

    # Add internal URL
    await async_process_ha_core_config(
        hass,
        {"internal_url": "https://internal.local"},
    )
    assert _get_internal_url(hass) == "https://internal.local"
    assert _get_internal_url(hass, allow_ip=False) == "https://internal.local"
    assert (
        _get_internal_url(hass, require_standard_port=True) == "https://internal.local"
    )
    assert _get_internal_url(hass, require_ssl=True) == "https://internal.local"

    # Add internal URL, mixed results
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://internal.local:8123"},
    )
    assert _get_internal_url(hass) == "http://internal.local:8123"
    assert _get_internal_url(hass, allow_ip=False) == "http://internal.local:8123"
    assert (
        _get_internal_url(hass, require_standard_port=True) == "https://example.local"
    )
    assert _get_internal_url(hass, require_ssl=True) == "https://example.local"

    # Add internal URL set to an IP
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://10.10.10.10:8123"},
    )
    assert _get_internal_url(hass) == "http://10.10.10.10:8123"
    assert _get_internal_url(hass, allow_ip=False) == "https://example.local"
    assert (
        _get_internal_url(hass, require_standard_port=True) == "https://example.local"
    )
    assert _get_internal_url(hass, require_ssl=True) == "https://example.local"


async def test_get_external_url_with_base_url_fallback(hass: HomeAssistant):
    """Test getting an external instance URL with the deprecated base_url fallback."""
    hass.config.api = Mock(use_ssl=False, port=8123, deprecated_base_url=None)
    assert hass.config.internal_url is None

    with pytest.raises(NoURLAvailableError):
        _get_external_url(hass)

    # Test with SSL and external domain on standard port
    hass.config.api = Mock(deprecated_base_url="https://example.com:443/")
    assert _get_external_url(hass) == "https://example.com"
    assert _get_external_url(hass, allow_ip=False) == "https://example.com"
    assert _get_external_url(hass, require_ssl=True) == "https://example.com"
    assert _get_external_url(hass, require_standard_port=True) == "https://example.com"

    # Add external URL
    await async_process_ha_core_config(
        hass,
        {"external_url": "https://external.example.com"},
    )
    assert _get_external_url(hass) == "https://external.example.com"
    assert _get_external_url(hass, allow_ip=False) == "https://external.example.com"
    assert (
        _get_external_url(hass, require_standard_port=True)
        == "https://external.example.com"
    )
    assert _get_external_url(hass, require_ssl=True) == "https://external.example.com"

    # Add external URL, mixed results
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://external.example.com:8123"},
    )
    assert _get_external_url(hass) == "http://external.example.com:8123"
    assert _get_external_url(hass, allow_ip=False) == "http://external.example.com:8123"
    assert _get_external_url(hass, require_standard_port=True) == "https://example.com"
    assert _get_external_url(hass, require_ssl=True) == "https://example.com"

    # Add external URL set to an IP
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://1.1.1.1:8123"},
    )
    assert _get_external_url(hass) == "http://1.1.1.1:8123"
    assert _get_external_url(hass, allow_ip=False) == "https://example.com"
    assert _get_external_url(hass, require_standard_port=True) == "https://example.com"
    assert _get_external_url(hass, require_ssl=True) == "https://example.com"


async def test_get_current_request_url_with_known_host(
    hass: HomeAssistant, current_request
):
    """Test getting current request URL with known hosts addresses."""
    hass.config.api = Mock(
        use_ssl=False, port=8123, local_ip="127.0.0.1", deprecated_base_url=None
    )
    assert hass.config.internal_url is None

    with pytest.raises(NoURLAvailableError):
        get_url(hass, require_current_request=True)

    # Ensure we accept localhost
    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="localhost"
    ):
        assert get_url(hass, require_current_request=True) == "http://localhost:8123"
        with pytest.raises(NoURLAvailableError):
            get_url(hass, require_current_request=True, require_ssl=True)
        with pytest.raises(NoURLAvailableError):
            get_url(hass, require_current_request=True, require_standard_port=True)

    # Ensure we accept local loopback ip (e.g., 127.0.0.1)
    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="127.0.0.8"
    ):
        assert get_url(hass, require_current_request=True) == "http://127.0.0.8:8123"
        with pytest.raises(NoURLAvailableError):
            get_url(hass, require_current_request=True, allow_ip=False)

    # Ensure hostname from Supervisor is accepted transparently
    mock_component(hass, "hassio")
    hass.components.hassio.is_hassio = Mock(return_value=True)
    hass.components.hassio.get_host_info = Mock(
        return_value={"hostname": "homeassistant"}
    )

    with patch(
        "homeassistant.helpers.network._get_request_host",
        return_value="homeassistant.local",
    ):
        assert (
            get_url(hass, require_current_request=True)
            == "http://homeassistant.local:8123"
        )

    with patch(
        "homeassistant.helpers.network._get_request_host",
        return_value="homeassistant",
    ):
        assert (
            get_url(hass, require_current_request=True) == "http://homeassistant:8123"
        )

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="unknown.local"
    ), pytest.raises(NoURLAvailableError):
        get_url(hass, require_current_request=True)


async def test_is_internal_request(hass: HomeAssistant):
    """Test if accessing an instance on its internal URL."""
    # Test with internal URL: http://example.local:8123
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    assert hass.config.internal_url == "http://example.local:8123"
    assert not is_internal_request(hass)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="example.local"
    ):
        assert is_internal_request(hass)

    with patch(
        "homeassistant.helpers.network._get_request_host",
        return_value="no_match.example.local",
    ):
        assert not is_internal_request(hass)

    # Test with internal URL: http://192.168.0.1:8123
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://192.168.0.1:8123"},
    )

    assert hass.config.internal_url == "http://192.168.0.1:8123"
    assert not is_internal_request(hass)

    with patch(
        "homeassistant.helpers.network._get_request_host", return_value="192.168.0.1"
    ):
        assert is_internal_request(hass)
