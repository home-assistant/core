"""The tests for the Home Assistant HTTP component."""
from ipaddress import ip_network
import logging
from unittest.mock import Mock, patch

import pytest

import homeassistant.components.http as http
from homeassistant.setup import async_setup_component
from homeassistant.util.ssl import server_context_intermediate, server_context_modern


@pytest.fixture
def mock_stack():
    """Mock extract stack."""
    with patch(
        "homeassistant.components.http.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/core/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/core/homeassistant/components/hue/light.py",
                lineno="23",
                line="self.light.is_on",
            ),
            Mock(
                filename="/home/paulus/core/homeassistant/components/http/__init__.py",
                lineno="157",
                line="base_url",
            ),
        ],
    ):
        yield


class TestView(http.HomeAssistantView):
    """Test the HTTP views."""

    name = "test"
    url = "/hello"

    async def get(self, request):
        """Return a get request."""
        return "hello"


async def test_registering_view_while_running(
    hass, aiohttp_client, aiohttp_unused_port
):
    """Test that we can register a view while the server is running."""
    await async_setup_component(
        hass, http.DOMAIN, {http.DOMAIN: {http.CONF_SERVER_PORT: aiohttp_unused_port()}}
    )

    await hass.async_start()
    # This raises a RuntimeError if app is frozen
    hass.http.register_view(TestView)


def test_api_base_url_with_domain(mock_stack):
    """Test setting API URL with domain."""
    api_config = http.ApiConfig("127.0.0.1", "example.com")
    assert api_config.base_url == "http://example.com:8123"


def test_api_base_url_with_ip(mock_stack):
    """Test setting API URL with IP."""
    api_config = http.ApiConfig("127.0.0.1", "1.1.1.1")
    assert api_config.base_url == "http://1.1.1.1:8123"


def test_api_base_url_with_ip_and_port(mock_stack):
    """Test setting API URL with IP and port."""
    api_config = http.ApiConfig("127.0.0.1", "1.1.1.1", 8124)
    assert api_config.base_url == "http://1.1.1.1:8124"


def test_api_base_url_with_protocol(mock_stack):
    """Test setting API URL with protocol."""
    api_config = http.ApiConfig("127.0.0.1", "https://example.com")
    assert api_config.base_url == "https://example.com:8123"


def test_api_base_url_with_protocol_and_port(mock_stack):
    """Test setting API URL with protocol and port."""
    api_config = http.ApiConfig("127.0.0.1", "https://example.com", 433)
    assert api_config.base_url == "https://example.com:433"


def test_api_base_url_with_ssl_enable(mock_stack):
    """Test setting API URL with use_ssl enabled."""
    api_config = http.ApiConfig("127.0.0.1", "example.com", use_ssl=True)
    assert api_config.base_url == "https://example.com:8123"


def test_api_base_url_with_ssl_enable_and_port(mock_stack):
    """Test setting API URL with use_ssl enabled and port."""
    api_config = http.ApiConfig("127.0.0.1", "1.1.1.1", use_ssl=True, port=8888)
    assert api_config.base_url == "https://1.1.1.1:8888"


def test_api_base_url_with_protocol_and_ssl_enable(mock_stack):
    """Test setting API URL with specific protocol and use_ssl enabled."""
    api_config = http.ApiConfig("127.0.0.1", "http://example.com", use_ssl=True)
    assert api_config.base_url == "http://example.com:8123"


def test_api_base_url_removes_trailing_slash(mock_stack):
    """Test a trialing slash is removed when setting the API URL."""
    api_config = http.ApiConfig("127.0.0.1", "http://example.com/")
    assert api_config.base_url == "http://example.com:8123"


def test_api_local_ip(mock_stack):
    """Test a trialing slash is removed when setting the API URL."""
    api_config = http.ApiConfig("127.0.0.1", "http://example.com/")
    assert api_config.local_ip == "127.0.0.1"


async def test_api_no_base_url(hass, mock_stack):
    """Test setting api url."""
    result = await async_setup_component(hass, "http", {"http": {}})
    assert result
    assert hass.config.api.base_url == "http://127.0.0.1:8123"


async def test_not_log_password(hass, aiohttp_client, caplog, legacy_auth):
    """Test access with password doesn't get logged."""
    assert await async_setup_component(hass, "api", {"http": {}})
    client = await aiohttp_client(hass.http.app)
    logging.getLogger("aiohttp.access").setLevel(logging.INFO)

    resp = await client.get("/api/", params={"api_password": "test-password"})

    assert resp.status == 401
    logs = caplog.text

    # Ensure we don't log API passwords
    assert "/api/" in logs
    assert "some-pass" not in logs


async def test_proxy_config(hass):
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass,
            "http",
            {
                "http": {
                    http.CONF_USE_X_FORWARDED_FOR: True,
                    http.CONF_TRUSTED_PROXIES: ["127.0.0.1"],
                }
            },
        )
        is True
    )


async def test_proxy_config_only_use_xff(hass):
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass, "http", {"http": {http.CONF_USE_X_FORWARDED_FOR: True}}
        )
        is not True
    )


async def test_proxy_config_only_trust_proxies(hass):
    """Test use_x_forwarded_for must config together with trusted_proxies."""
    assert (
        await async_setup_component(
            hass, "http", {"http": {http.CONF_TRUSTED_PROXIES: ["127.0.0.1"]}}
        )
        is not True
    )


async def test_ssl_profile_defaults_modern(hass):
    """Test default ssl profile."""
    assert await async_setup_component(hass, "http", {}) is True

    hass.http.ssl_certificate = "bla"

    with patch("ssl.SSLContext.load_cert_chain"), patch(
        "homeassistant.util.ssl.server_context_modern",
        side_effect=server_context_modern,
    ) as mock_context:
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1


async def test_ssl_profile_change_intermediate(hass):
    """Test setting ssl profile to intermediate."""
    assert (
        await async_setup_component(
            hass, "http", {"http": {"ssl_profile": "intermediate"}}
        )
        is True
    )

    hass.http.ssl_certificate = "bla"

    with patch("ssl.SSLContext.load_cert_chain"), patch(
        "homeassistant.util.ssl.server_context_intermediate",
        side_effect=server_context_intermediate,
    ) as mock_context:
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1


async def test_ssl_profile_change_modern(hass):
    """Test setting ssl profile to modern."""
    assert (
        await async_setup_component(hass, "http", {"http": {"ssl_profile": "modern"}})
        is True
    )

    hass.http.ssl_certificate = "bla"

    with patch("ssl.SSLContext.load_cert_chain"), patch(
        "homeassistant.util.ssl.server_context_modern",
        side_effect=server_context_modern,
    ) as mock_context:
        await hass.async_start()
        await hass.async_block_till_done()

    assert len(mock_context.mock_calls) == 1


async def test_cors_defaults(hass):
    """Test the CORS default settings."""
    with patch("homeassistant.components.http.setup_cors") as mock_setup:
        assert await async_setup_component(hass, "http", {})

    assert len(mock_setup.mock_calls) == 1
    assert mock_setup.mock_calls[0][1][1] == ["https://cast.home-assistant.io"]


async def test_storing_config(hass, aiohttp_client, aiohttp_unused_port):
    """Test that we store last working config."""
    config = {
        http.CONF_SERVER_PORT: aiohttp_unused_port(),
        "use_x_forwarded_for": True,
        "trusted_proxies": ["192.168.1.100"],
    }

    assert await async_setup_component(hass, http.DOMAIN, {http.DOMAIN: config})

    await hass.async_start()
    restored = await hass.components.http.async_get_last_config()
    restored["trusted_proxies"][0] = ip_network(restored["trusted_proxies"][0])

    assert restored == http.HTTP_SCHEMA(config)


async def test_use_of_base_url(hass):
    """Test detection base_url usage when called without integration context."""
    await async_setup_component(hass, "http", {"http": {}})
    with patch(
        "homeassistant.components.http.extract_stack",
        return_value=[
            Mock(
                filename="/home/frenck/homeassistant/core.py",
                lineno="21",
                line="do_something()",
            ),
            Mock(
                filename="/home/frenck/homeassistant/core.py",
                lineno="42",
                line="url = hass.config.api.base_url",
            ),
            Mock(
                filename="/home/frenck/example/client.py",
                lineno="21",
                line="something()",
            ),
        ],
    ), pytest.raises(RuntimeError):
        hass.config.api.base_url


async def test_use_of_base_url_integration(hass, caplog):
    """Test detection base_url usage when called with integration context."""
    await async_setup_component(hass, "http", {"http": {}})
    with patch(
        "homeassistant.components.http.extract_stack",
        return_value=[
            Mock(
                filename="/home/frenck/homeassistant/core.py",
                lineno="21",
                line="do_something()",
            ),
            Mock(
                filename="/home/frenck/homeassistant/components/example/__init__.py",
                lineno="42",
                line="url = hass.config.api.base_url",
            ),
            Mock(
                filename="/home/frenck/example/client.py",
                lineno="21",
                line="something()",
            ),
        ],
    ):
        assert hass.config.api.base_url == "http://127.0.0.1:8123"

    assert (
        "Detected use of deprecated `base_url` property, use `homeassistant.helpers.network.get_url` method instead. Please report issue for example using this method at homeassistant/components/example/__init__.py, line 42: url = hass.config.api.base_url"
        in caplog.text
    )


async def test_use_of_base_url_integration_webhook(hass, caplog):
    """Test detection base_url usage when called with integration context."""
    await async_setup_component(hass, "http", {"http": {}})
    with patch(
        "homeassistant.components.http.extract_stack",
        return_value=[
            Mock(
                filename="/home/frenck/homeassistant/core.py",
                lineno="21",
                line="do_something()",
            ),
            Mock(
                filename="/home/frenck/homeassistant/components/example/__init__.py",
                lineno="42",
                line="url = hass.config.api.base_url",
            ),
            Mock(
                filename="/home/frenck/homeassistant/components/webhook/__init__.py",
                lineno="42",
                line="return get_url(hass)",
            ),
            Mock(
                filename="/home/frenck/example/client.py",
                lineno="21",
                line="something()",
            ),
        ],
    ):
        assert hass.config.api.base_url == "http://127.0.0.1:8123"

    assert (
        "Detected use of deprecated `base_url` property, use `homeassistant.helpers.network.get_url` method instead. Please report issue for example using this method at homeassistant/components/example/__init__.py, line 42: url = hass.config.api.base_url"
        in caplog.text
    )


async def test_use_of_base_url_custom_component(hass, caplog):
    """Test detection base_url usage when called with custom component context."""
    await async_setup_component(hass, "http", {"http": {}})
    with patch(
        "homeassistant.components.http.extract_stack",
        return_value=[
            Mock(
                filename="/home/frenck/homeassistant/core.py",
                lineno="21",
                line="do_something()",
            ),
            Mock(
                filename="/home/frenck/.homeassistant/custom_components/example/__init__.py",
                lineno="42",
                line="url = hass.config.api.base_url",
            ),
            Mock(
                filename="/home/frenck/example/client.py",
                lineno="21",
                line="something()",
            ),
        ],
    ):
        assert hass.config.api.base_url == "http://127.0.0.1:8123"

    assert (
        "Detected use of deprecated `base_url` property, use `homeassistant.helpers.network.get_url` method instead. Please report issue to the custom component author for example using this method at custom_components/example/__init__.py, line 42: url = hass.config.api.base_url"
        in caplog.text
    )
