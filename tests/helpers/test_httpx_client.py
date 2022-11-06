"""Test the httpx client helper."""

from unittest.mock import Mock, patch

import httpx
import pytest

from homeassistant.core import EVENT_HOMEASSISTANT_CLOSE
import homeassistant.helpers.httpx_client as client


async def test_get_async_client_with_ssl(hass):
    """Test init async client with ssl."""
    client.get_async_client(hass)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT], httpx.AsyncClient)


async def test_get_async_client_without_ssl(hass):
    """Test init async client without ssl."""
    client.get_async_client(hass, verify_ssl=False)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY], httpx.AsyncClient)


async def test_create_async_httpx_client_with_ssl_and_cookies(hass):
    """Test init async client with ssl and cookies."""
    client.get_async_client(hass)

    httpx_client = client.create_async_httpx_client(hass, cookies={"bla": True})
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT] != httpx_client


async def test_create_async_httpx_client_without_ssl_and_cookies(hass):
    """Test init async client without ssl and cookies."""
    client.get_async_client(hass, verify_ssl=False)

    httpx_client = client.create_async_httpx_client(
        hass, verify_ssl=False, cookies={"bla": True}
    )
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY] != httpx_client


async def test_get_async_client_cleanup(hass):
    """Test init async client with ssl."""
    client.get_async_client(hass)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT], httpx.AsyncClient)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT].is_closed


async def test_get_async_client_cleanup_without_ssl(hass):
    """Test init async client without ssl."""
    client.get_async_client(hass, verify_ssl=False)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY], httpx.AsyncClient)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY].is_closed


async def test_get_async_client_patched_close(hass):
    """Test closing the async client does not work."""

    with patch("httpx.AsyncClient.aclose") as mock_aclose:
        httpx_session = client.get_async_client(hass)
        assert isinstance(hass.data[client.DATA_ASYNC_CLIENT], httpx.AsyncClient)

        with pytest.raises(RuntimeError):
            await httpx_session.aclose()

        assert mock_aclose.call_count == 0


async def test_get_async_client_context_manager(hass):
    """Test using the async client with a context manager does not close the session."""

    with patch("httpx.AsyncClient.aclose") as mock_aclose:
        httpx_session = client.get_async_client(hass)
        assert isinstance(hass.data[client.DATA_ASYNC_CLIENT], httpx.AsyncClient)

        async with httpx_session:
            pass

        assert mock_aclose.call_count == 0


@patch("homeassistant.helpers.frame._REPORTED_INTEGRATIONS", set())
async def test_warning_close_session_integration(hass, caplog):
    """Test log warning message when closing the session from integration context."""
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
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
        ],
    ):
        httpx_session = client.get_async_client(hass)
        await httpx_session.aclose()

    assert (
        "Detected integration that closes the Home Assistant httpx client. "
        "Please report issue for hue using this method at "
        "homeassistant/components/hue/light.py, line 23: await session.aclose()"
    ) in caplog.text


@patch("homeassistant.helpers.frame._REPORTED_INTEGRATIONS", set())
async def test_warning_close_session_custom(hass, caplog):
    """Test log warning message when closing the session from custom context."""
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
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
        ],
    ):
        httpx_session = client.get_async_client(hass)
        await httpx_session.aclose()
    assert (
        "Detected integration that closes the Home Assistant httpx client. "
        "Please report issue to the custom integration author for hue using this method at "
        "custom_components/hue/light.py, line 23: await session.aclose()" in caplog.text
    )
