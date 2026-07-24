"""Test the httpx client helper."""

from collections.abc import Callable, Generator
from functools import partial
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client as client
from homeassistant.util.ssl import SSL_ALPN_HTTP11, SSL_ALPN_HTTP11_HTTP2

from tests.common import (
    MockConfigEntry,
    MockModule,
    extract_stack_to_frame,
    mock_config_flow,
    mock_integration,
    mock_platform,
)


@pytest.fixture
def mock_comp_flow() -> Generator[None]:
    """Mock a config flow for the comp integration."""

    class MockConfigFlow:
        """Mock the comp config flow."""

        VERSION = 1
        MINOR_VERSION = 1

    with mock_config_flow("comp", MockConfigFlow):
        yield


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


@pytest.mark.parametrize(
    (
        "client_factory",
        "listener_delta_after_setup",
        "closed_after_unload",
        "listener_delta_after_unload",
        "closed_after_close_event",
    ),
    [
        pytest.param(
            client.create_async_httpx_client, 1, True, 0, True, id="created_client"
        ),
        pytest.param(client.get_async_client, 1, False, 1, True, id="shared_client"),
        pytest.param(
            partial(client.create_async_httpx_client, auto_cleanup=False),
            0,
            False,
            0,
            False,
            id="no_auto_cleanup",
        ),
    ],
)
@pytest.mark.usefixtures("mock_comp_flow")
async def test_httpx_client_cleanup_on_entry_unload(
    hass: HomeAssistant,
    client_factory: Callable[[HomeAssistant], httpx.AsyncClient],
    listener_delta_after_setup: int,
    closed_after_unload: bool,
    listener_delta_after_unload: int,
    closed_after_close_event: bool,
) -> None:
    """Test cleanup of a client created during config entry setup."""
    baseline = hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_CLOSE, 0)
    created: list[httpx.AsyncClient] = []

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        created.append(client_factory(hass))
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=async_setup_entry,
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    entry = MockConfigEntry(domain="comp")
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert (
        hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_CLOSE, 0)
        == baseline + listener_delta_after_setup
    )
    assert not created[0].is_closed

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert created[0].is_closed is closed_after_unload
    assert (
        hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_CLOSE, 0)
        == baseline + listener_delta_after_unload
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    assert created[0].is_closed is closed_after_close_event


@pytest.mark.usefixtures("mock_comp_flow")
async def test_get_async_client_survives_entry_unload(hass: HomeAssistant) -> None:
    """Test the shared client is not entry-bound even when first created in setup."""
    shared: list[httpx.AsyncClient] = []

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        shared.append(client.get_async_client(hass))
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=async_setup_entry,
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    entry = MockConfigEntry(domain="comp")
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert shared[0] is hass.data[client.DATA_ASYNC_CLIENT][(True, SSL_ALPN_HTTP11)]
    assert not shared[0].is_closed
    assert client.get_async_client(hass) is shared[0]


async def test_create_async_httpx_client_outside_entry_cleanup(
    hass: HomeAssistant,
) -> None:
    """Test a client created outside entry setup is closed on homeassistant_close."""
    baseline = hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_CLOSE, 0)

    httpx_client = client.create_async_httpx_client(hass)
    assert hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_CLOSE, 0) == baseline + 1
    assert not httpx_client.is_closed

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    assert httpx_client.is_closed
