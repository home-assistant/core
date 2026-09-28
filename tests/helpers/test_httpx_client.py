"""Test the httpx client helper."""

from collections.abc import Callable
from pathlib import Path
import ssl
from unittest.mock import Mock, patch

import certifi
import httpcore2
from httpcore2._backends.mock import AsyncMockBackend
import httpx2
import pytest
import truststore

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client as client
from homeassistant.util.ssl import (
    SSL_ALPN_HTTP11,
    SSL_ALPN_HTTP11_HTTP2,
    SSLCipherList,
    client_context,
)

from tests.common import MockModule, extract_stack_to_frame, mock_integration


async def test_get_async_client_with_ssl(hass: HomeAssistant) -> None:
    """Test init async client with ssl."""
    client.get_async_client(hass)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
        httpx2.AsyncClient,
    )


async def test_get_async_client_without_ssl(hass: HomeAssistant) -> None:
    """Test init async client without ssl."""
    client.get_async_client(hass, verify_ssl=False)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)],
        httpx2.AsyncClient,
    )


async def test_create_async_httpx_client_with_ssl_and_cookies(
    hass: HomeAssistant,
) -> None:
    """Test init async client with ssl and cookies."""
    client.get_async_client(hass)

    httpx_client = client.create_async_httpx_client(hass, cookies={"bla": True})
    assert isinstance(httpx_client, httpx2.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)] != httpx_client


async def test_create_async_httpx_client_without_ssl_and_cookies(
    hass: HomeAssistant,
) -> None:
    """Test init async client without ssl and cookies."""
    client.get_async_client(hass, verify_ssl=False)

    httpx_client = client.create_async_httpx_client(
        hass, verify_ssl=False, cookies={"bla": True}
    )
    assert isinstance(httpx_client, httpx2.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)] != httpx_client


async def test_create_async_httpx_client_default_headers(
    hass: HomeAssistant,
) -> None:
    """Test init async client with default headers."""
    httpx_client = client.create_async_httpx_client(hass)
    assert isinstance(httpx_client, httpx2.AsyncClient)
    assert httpx_client.headers[client.USER_AGENT] == client.SERVER_SOFTWARE


async def test_create_async_httpx_client_with_headers(
    hass: HomeAssistant,
) -> None:
    """Test init async client with headers."""
    httpx_client = client.create_async_httpx_client(hass, headers={"x-test": "true"})
    assert isinstance(httpx_client, httpx2.AsyncClient)
    assert httpx_client.headers["x-test"] == "true"
    # Default headers are preserved
    assert httpx_client.headers[client.USER_AGENT] == client.SERVER_SOFTWARE


async def test_get_async_client_cleanup(hass: HomeAssistant) -> None:
    """Test init async client with ssl."""
    client.get_async_client(hass)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
        httpx2.AsyncClient,
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)].is_closed


async def test_get_async_client_cleanup_without_ssl(hass: HomeAssistant) -> None:
    """Test init async client without ssl."""
    client.get_async_client(hass, verify_ssl=False)

    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)],
        httpx2.AsyncClient,
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT][(False, SSL_ALPN_HTTP11)].is_closed


async def test_get_async_client_patched_close(hass: HomeAssistant) -> None:
    """Test closing the async client does not work."""

    with patch("httpx2.AsyncClient.aclose") as mock_aclose:
        httpx_session = client.get_async_client(hass)
        assert isinstance(
            hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
            httpx2.AsyncClient,
        )

        with pytest.raises(RuntimeError):
            await httpx_session.aclose()

        assert mock_aclose.call_count == 0


async def test_get_async_client_context_manager(hass: HomeAssistant) -> None:
    """Test using the async client with a context manager does not close the session."""

    with patch("httpx2.AsyncClient.aclose") as mock_aclose:
        httpx_session = client.get_async_client(hass)
        assert isinstance(
            hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)],
            httpx2.AsyncClient,
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
        httpx2.AsyncClient,
    )
    assert isinstance(
        hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11_HTTP2)],
        httpx2.AsyncClient,
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
        httpx2.AsyncClient,
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
        httpx2.AsyncClient,
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
    assert isinstance(http1_client, httpx2.AsyncClient)
    assert isinstance(http2_client, httpx2.AsyncClient)


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


DEFAULT_SSL_CONTEXT_FACTORIES = [
    pytest.param(httpx2.create_ssl_context, id="httpx2"),
    pytest.param(httpcore2.default_ssl_context, id="httpcore2"),
]


@pytest.fixture
def ca_bundle(tmp_path: Path) -> Path:
    """Return a CA bundle containing only the first certifi certificate."""
    certifi_bundle = Path(certifi.where()).read_text(encoding="utf-8")
    end_marker = "-----END CERTIFICATE-----"
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text(
        certifi_bundle[: certifi_bundle.index(end_marker)] + end_marker,
        encoding="utf-8",
    )
    return ca_bundle


@pytest.mark.parametrize("create_context", DEFAULT_SSL_CONTEXT_FACTORIES)
def test_default_ssl_context_uses_certifi(
    monkeypatch: pytest.MonkeyPatch, create_context: Callable[[], ssl.SSLContext]
) -> None:
    """Test httpx2 default SSL contexts use certifi instead of truststore."""
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    expected = ssl.create_default_context(cafile=certifi.where())

    context = create_context()

    assert context.cert_store_stats() == expected.cert_store_stats()
    # truststore reloads the system CA store on every handshake
    with patch.object(ssl.SSLContext, "set_default_verify_paths") as mock_load:
        context.wrap_bio(ssl.MemoryBIO(), ssl.MemoryBIO(), server_hostname="a.b")
    mock_load.assert_not_called()


@pytest.mark.parametrize("create_context", DEFAULT_SSL_CONTEXT_FACTORIES)
def test_default_ssl_context_honors_ssl_cert_file(
    monkeypatch: pytest.MonkeyPatch,
    ca_bundle: Path,
    create_context: Callable[[], ssl.SSLContext],
) -> None:
    """Test httpx2 default SSL contexts still honor SSL_CERT_FILE."""
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_bundle))

    assert create_context().cert_store_stats()["x509_ca"] == 1


def test_create_ssl_context_without_trust_env(
    monkeypatch: pytest.MonkeyPatch, ca_bundle: Path
) -> None:
    """Test CA environment variables are ignored when trust_env is False."""
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_bundle))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_bundle))
    expected = ssl.create_default_context(cafile=certifi.where())

    context = httpx2.create_ssl_context(trust_env=False)

    assert context.cert_store_stats() == expected.cert_store_stats()


@pytest.mark.parametrize(
    "protocol",
    [
        pytest.param(ssl.PROTOCOL_TLS_CLIENT, id="client"),
        pytest.param(ssl.PROTOCOL_TLS_SERVER, id="server"),
    ],
)
def test_truststore_ssl_context_subclass(protocol: ssl._SSLMethod) -> None:
    """Test subclassing and isinstance checks on truststore.SSLContext work."""

    class CustomSSLContext(truststore.SSLContext):
        """Custom SSL context, as some libraries define."""

    expected = ssl.create_default_context(cafile=certifi.where())

    context = CustomSSLContext(protocol)

    assert isinstance(context, truststore.SSLContext)
    assert context.protocol == protocol
    assert context.cert_store_stats() == expected.cert_store_stats()
    assert context.verify_flags == expected.verify_flags


@pytest.mark.parametrize(
    ("alpn_protocols", "http2"),
    [
        pytest.param(SSL_ALPN_HTTP11, False, id="http1"),
        pytest.param(SSL_ALPN_HTTP11_HTTP2, True, id="http2"),
    ],
)
async def test_httpcore2_does_not_mutate_ssl_context_alpn(
    alpn_protocols: tuple[str, ...], http2: bool
) -> None:
    """Test httpcore2 sets the same ALPN protocols HA preconfigured."""
    context = client_context(SSLCipherList.PYTHON_DEFAULT, alpn_protocols)
    backend = AsyncMockBackend(
        [b"HTTP/1.1 200 OK\r\n", b"Content-Length: 0\r\n", b"\r\n"]
    )

    with patch.object(
        ssl.SSLContext, "set_alpn_protocols", autospec=True
    ) as mock_set_alpn:
        async with httpcore2.AsyncConnectionPool(
            ssl_context=context, http2=http2, network_backend=backend
        ) as pool:
            await pool.request("GET", "https://example.com/")

    mock_set_alpn.assert_called_once_with(context, list(alpn_protocols))


@pytest.mark.parametrize("create_context", DEFAULT_SSL_CONTEXT_FACTORIES)
def test_default_ssl_context_honors_sslkeylogfile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    create_context: Callable[[], ssl.SSLContext],
) -> None:
    """Test httpx2 default SSL contexts honor SSLKEYLOGFILE, like httpx did."""
    keylog_file = tmp_path / "keylog.txt"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog_file))

    assert create_context().keylog_filename == str(keylog_file)
