"""Test the httpx client helper."""

from functools import partial

import httpx
import pytest

from homeassistant.core import EVENT_HOMEASSISTANT_CLOSE
import homeassistant.helpers.httpx_client as client

from tests.async_mock import Mock, patch


async def test_async_get_async_client_with_ssl(hass):
    """Test init async client with ssl."""
    client.async_get_async_client(hass)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT], httpx.AsyncClient)


async def test_async_get_async_client_without_ssl(hass):
    """Test init async client without ssl."""
    client.async_get_async_client(hass, verify_ssl=False)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY], httpx.AsyncClient)


async def test_async_create_async_httpx_client_with_ssl_and_cookies(hass):
    """Test init async client with ssl and cookies."""
    client.async_get_async_client(hass)

    httpx_client = client.async_create_async_httpx_client(hass, cookies={"bla": True})
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT] != httpx_client


async def test_async_create_async_httpx_client_without_ssl_and_cookies(hass):
    """Test init async client without ssl and cookies."""
    client.async_get_async_client(hass, verify_ssl=False)

    httpx_client = client.async_create_async_httpx_client(
        hass, verify_ssl=False, cookies={"bla": True}
    )
    assert isinstance(httpx_client, httpx.AsyncClient)
    assert hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY] != httpx_client


async def test_async_get_async_client_cleanup(hass):
    """Test init async client with ssl."""
    client.async_get_async_client(hass)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT], httpx.AsyncClient)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT].is_closed


async def test_async_get_async_client_cleanup_without_ssl(hass):
    """Test init async client without ssl."""
    client.async_get_async_client(hass, verify_ssl=False)

    assert isinstance(hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY], httpx.AsyncClient)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_ASYNC_CLIENT_NOVERIFY].is_closed


async def test_async_get_async_client_patched_close(hass):
    """Test closing the async client does not work."""

    with patch("httpx.AsyncClient.aclose") as mock_aclose:
        httpx_session = client.async_get_async_client(hass)
        assert isinstance(hass.data[client.DATA_ASYNC_CLIENT], httpx.AsyncClient)

        with pytest.raises(RuntimeError):
            await httpx_session.aclose()

        assert mock_aclose.call_count == 0


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
        httpx_session = client.async_get_async_client(hass)
        await httpx_session.aclose()

    assert (
        "Detected integration that closes the Home Assistant httpx client. "
        "Please report issue for hue using this method at "
        "homeassistant/components/hue/light.py, line 23: await session.aclose()"
    ) in caplog.text


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
        httpx_session = client.async_get_async_client(hass)
        await httpx_session.aclose()
    assert (
        "Detected integration that closes the Home Assistant httpx client. "
        "Please report issue to the custom component author for hue using this method at "
        "custom_components/hue/light.py, line 23: await session.aclose()" in caplog.text
    )


async def test_async_get_client_with_ssl(hass):
    """Test init client with ssl from async."""
    client.async_get_client(hass)

    assert isinstance(hass.data[client.DATA_CLIENT], httpx.Client)


async def test_get_client_with_ssl(hass):
    """Test init client with ssl."""

    await hass.async_add_executor_job(client.get_client, hass)

    assert isinstance(hass.data[client.DATA_CLIENT], httpx.Client)


async def test_async_get_client_without_ssl(hass):
    """Test init client without ssl from async."""
    client.async_get_client(hass, verify_ssl=False)

    assert isinstance(hass.data[client.DATA_CLIENT_NOVERIFY], httpx.Client)


async def test_get_client_without_ssl(hass):
    """Test init client without ssl."""

    await hass.async_add_executor_job(
        partial(client.get_client, hass, verify_ssl=False)
    )

    assert isinstance(hass.data[client.DATA_CLIENT_NOVERIFY], httpx.Client)


async def test_create_httpx_client_with_ssl_and_cookies(hass):
    """Test init client with ssl and cookies."""
    client.async_get_client(hass)

    httpx_client = await hass.async_add_executor_job(
        partial(client.create_httpx_client, hass, cookies={"bla": True})
    )
    assert isinstance(httpx_client, httpx.Client)
    assert hass.data[client.DATA_CLIENT] != httpx_client


async def test_async_get_client_cleanup(hass):
    """Test init client with ssl."""
    client.async_get_client(hass)

    assert isinstance(hass.data[client.DATA_CLIENT], httpx.Client)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_CLIENT].is_closed


async def test_async_get_client_cleanup_without_ssl(hass):
    """Test init client without ssl."""
    client.async_get_client(hass, verify_ssl=False)

    assert isinstance(hass.data[client.DATA_CLIENT_NOVERIFY], httpx.Client)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_CLIENT_NOVERIFY].is_closed


async def test_async_get_client_patched_close(hass):
    """Test closing the client does not work."""

    with patch("httpx.Client.close") as mock_close:
        httpx_session = client.async_get_client(hass)
        assert isinstance(hass.data[client.DATA_CLIENT], httpx.Client)

        with pytest.raises(RuntimeError):
            await hass.async_add_executor_job(httpx_session.close)

        assert mock_close.call_count == 0
