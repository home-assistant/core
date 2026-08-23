"""Test the httpx client helper."""

from unittest.mock import Mock, patch

import httpx
import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client as client
from homeassistant.util.ssl import SSL_ALPN_HTTP11, SSL_ALPN_HTTP11_HTTP2

from tests.common import MockModule, extract_stack_to_frame, mock_integration


async def test_get_async_client_with_ssl(hass: HomeAssistant) -> None:
    """Test init async client with ssl."""
    client.get_async_client(hass)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
        httpx.AsyncClient,
    )


async def test_get_async_client_without_ssl(hass: HomeAssistant) -> None:
    """Test init async client without ssl."""
    client.get_async_client(hass, verify_ssl=False)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)],
        httpx.AsyncClient,
    )


async def test_create_async_httpx_client_with_ssl_and_cookies(
    hass: HomeAssistant,
) -> None:
    """Test init async client with ssl and cookies."""
    client.get_async_client(hass)

    httpx_client = client.create_async_httpx_client(hass, cookies={"bla": True})
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)] != httpx_client


async def test_create_async_httpx_client_without_ssl_and_cookies(
    hass: HomeAssistant,
) -> None:
    """Test init async client without ssl and cookies."""
    client.get_async_client(hass, verify_ssl=False)

    httpx_client = client.create_async_httpx_client(
        hass, verify_ssl=False, cookies={"bla": True}
    )
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)] != httpx_client


async def test_create_async_httpx_client_default_headers(
    hass: HomeAssistant,
) -> None:
    """Test init async client with default headers."""
    httpx_client = client.create_async_httpx_client(hass)
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert httpx_client.headers[client.USER_AGENT] == client.SERVER_SOFTWARE


async def test_create_async_httpx_client_with_headers(
    hass: HomeAssistant,
) -> None:
    """Test init async client with headers."""
    httpx_client = client.create_async_httpx_client(hass, headers={"x-test": "true"})
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert httpx_client.headers["x-test"] == "true"
    # Default headers are preserved
    assert httpx_client.headers[client.USER_AGENT] == client.SERVER_SOFTWARE


async def test_get_async_client_cleanup(hass: HomeAssistant) -> None:
    """Test init async client with ssl."""
    client.get_async_client(hass)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
        httpx.AsyncClient,
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)].is_closed


async def test_get_async_client_cleanup_without_ssl(hass: HomeAssistant) -> None:
    """Test init async client without ssl."""
    client.get_async_client(hass, verify_ssl=False)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)],
        httpx.AsyncClient,
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)].is_closed


async def test_get_async_client_patched_close(hass: HomeAssistant) -> None:
    """Test closing the async client does not work."""

    with patch("httpx.AsyncClient.aclose") as mock_aclose:
        httpx_session = client.get_async_client(hass)
        assert isinstance(
            hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
            httpx.AsyncClient,
        )

        with pytest.raises(RuntimeError):
            await httpx_session.aclose()

        assert mock_aclose.call_count == 0


async def test_get_async_client_context_manager(hass: HomeAssistant) -> None:
    """Test using the async client with a context manager does not close the session."""

    with patch("httpx.AsyncClient.aclose") as mock_aclose:
        httpx_session = client.get_async_client(hass)
        assert isinstance(
            hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
            httpx.AsyncClient,
        )

        async with httpx_session:
            pass

        assert mock_aclose.call_count == 0


async def test_get_async_client_http2(hass: HomeAssistant) -> None:
    """Test init async client with HTTP/2 support."""
    http1_client = client.get_async_client(hass)
    http2_client = client.get_async_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2)

    # HTTP/1.1 and HTTP/2 clients should be different (different SSL contexts)
    assert http1_client is not http2_client
    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
        httpx.AsyncClient,
    )
    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11_HTTP2)],
        httpx.AsyncClient,
    )

    # Same parameters should return cached client
    assert client.get_async_client(hass) is http1_client
    assert (
        client.get_async_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2)
        is http2_client
    )


async def test_get_async_client_http2_cleanup(hass: HomeAssistant) -> None:
    """Test cleanup of HTTP/2 async client."""
    client.get_async_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11_HTTP2)],
        httpx.AsyncClient,
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11_HTTP2)].is_closed


async def test_get_async_client_http2_without_ssl(hass: HomeAssistant) -> None:
    """Test init async client with HTTP/2 and without SSL."""
    http2_client = client.get_async_client(
        hass, verify_ssl=False, alpn_protocols=SSL_ALPN_HTTP11_HTTP2
    )

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11_HTTP2)],
        httpx.AsyncClient,
    )

    # Same parameters should return cached client
    assert (
        client.get_async_client(
            hass, verify_ssl=False, alpn_protocols=SSL_ALPN_HTTP11_HTTP2
        )
        is http2_client
    )


async def test_create_async_httpx_client_http2(hass: HomeAssistant) -> None:
    """Test create async client with HTTP/2 uses correct ALPN protocols."""
    http1_client = client.create_async_httpx_client(hass)
    http2_client = client.create_async_httpx_client(
        hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2
    )

    # Different clients (not cached)
    assert http1_client is not http2_client

    # Both should be valid clients
    assert isinstance(http1_client, httpx.AsyncClient)
    assert isinstance(http2_client, httpx.AsyncClient)


async def test_warning_close_session_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test log warning message when closing the session from integration context."""
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.aclose()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename="/home/paulus/homeassistant/components/hue/light.py",
                        lineno="23",
                        line="await session.aclose()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        httpx_session = client.get_async_client(hass)
        await httpx_session.aclose()

    assert (
        "Detected that integration 'hue' closes the Home Assistant httpx client at "
        "homeassistant/components/hue/light.py, line 23: await session.aclose(). "
        "Please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text


async def test_warning_close_session_custom(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test log warning message when closing the session from custom context."""
    mock_integration(hass, MockModule("hue"), built_in=False)
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.aclose()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename="/home/paulus/config/custom_components/hue/light.py",
                        lineno="23",
                        line="await session.aclose()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        httpx_session = client.get_async_client(hass)
        await httpx_session.aclose()
    assert (
        "Detected that custom integration 'hue' closes the Home Assistant httpx client "
        "at custom_components/hue/light.py, line 23: await session.aclose(). "
        "Please report it to the author of the 'hue' custom integration"
    ) in caplog.text
