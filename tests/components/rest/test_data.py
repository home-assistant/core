"""Test REST data module logging improvements."""

from datetime import timedelta
import logging
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.rest import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_rest_data_log_warning_on_error_status(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that warning is logged for error status codes."""
    # Mock a 403 response with HTML content
    aioclient_mock.get(
        "http://example.com/api",
        status=403,
        text="<html><body>Access Denied</body></html>",
        headers={"Content-Type": "text/html"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.test }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check that warning was logged
    assert (
        "REST request to http://example.com/api returned status 403 "
        "with text/html response" in caplog.text
    )
    assert "<html><body>Access Denied</body></html>" in caplog.text


async def test_rest_data_no_warning_on_200_with_wrong_content_type(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that no warning is logged for 200 status with wrong content."""
    # Mock a 200 response with HTML - users might still want to parse this
    aioclient_mock.get(
        "http://example.com/api",
        status=200,
        text="<p>This is HTML, not JSON!</p>",
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Should NOT warn for 200 status, even with HTML content type
    assert (
        "REST request to http://example.com/api returned status 200" not in caplog.text
    )


async def test_rest_data_with_incorrect_charset_in_header(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that we can handle sites which provides an incorrect charset."""
    aioclient_mock.get(
        "http://example.com/api",
        status=200,
        text="<p>Some html</p>",
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "encoding": "windows-1250",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    with patch(
        "tests.test_util.aiohttp.AiohttpClientMockResponse.text",
        side_effect=UnicodeDecodeError("utf-8", b"", 1, 0, ""),
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    log_text = "Response charset came back as utf-8 but could not be decoded, continue with configured encoding windows-1250."
    assert log_text in caplog.text

    caplog.clear()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Only log once as we only try once with automatic decoding
    assert log_text not in caplog.text


async def test_rest_data_no_warning_on_success_json(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that no warning is logged for successful JSON responses."""
    # Mock a successful JSON response
    aioclient_mock.get(
        "http://example.com/api",
        status=200,
        json={"status": "ok", "value": 42},
        headers={"Content-Type": "application/json"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.value }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check that no warning was logged
    assert "REST request to http://example.com/api returned status" not in caplog.text


async def test_rest_data_no_warning_on_success_xml(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that no warning is logged for successful XML responses."""
    # Mock a successful XML response
    aioclient_mock.get(
        "http://example.com/api",
        status=200,
        text='<?xml version="1.0"?><root><value>42</value></root>',
        headers={"Content-Type": "application/xml"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.root.value }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check that no warning was logged
    assert "REST request to http://example.com/api returned status" not in caplog.text


async def test_rest_data_warning_truncates_long_responses(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that warning truncates very long response bodies."""
    # Create a very long error message
    long_message = "Error: " + "x" * 1000

    aioclient_mock.get(
        "http://example.com/api",
        status=500,
        text=long_message,
        headers={"Content-Type": "text/plain"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.test }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check that warning was logged with truncation
    # Set the logger filter to only check our specific logger
    caplog.set_level(logging.WARNING, logger="homeassistant.components.rest.data")

    # Verify the truncated warning appears
    assert (
        "REST request to http://example.com/api returned status 500 "
        "with text/plain response: Error: " + "x" * 493 + "..." in caplog.text
    )


async def test_rest_data_debug_logging_shows_response_details(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that debug logging shows response details."""
    caplog.set_level(logging.DEBUG)

    aioclient_mock.get(
        "http://example.com/api",
        status=200,
        json={"test": "data"},
        headers={"Content-Type": "application/json"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.test }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check debug log
    assert (
        "REST response from http://example.com/api: status=200, "
        "content-type=application/json, length=" in caplog.text
    )


async def test_rest_data_no_content_type_header(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of responses without Content-Type header."""
    caplog.set_level(logging.DEBUG)

    # Mock response without Content-Type header
    aioclient_mock.get(
        "http://example.com/api",
        status=200,
        text="plain text response",
        headers={},  # No Content-Type
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check debug log shows "not set"
    assert "content-type=not set" in caplog.text
    # No warning for 200 with missing content-type
    assert "REST request to http://example.com/api returned status" not in caplog.text


async def test_rest_data_real_world_bom_blocking_scenario(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test real-world scenario where BOM blocks with HTML response."""
    # Mock BOM blocking response
    bom_block_html = "<p>Your access is blocked due to automated access</p>"

    aioclient_mock.get(
        "http://www.bom.gov.au/fwo/IDN60901/IDN60901.94767.json",
        status=403,
        text=bom_block_html,
        headers={"Content-Type": "text/html"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": ("http://www.bom.gov.au/fwo/IDN60901/IDN60901.94767.json"),
                "method": "GET",
                "sensor": [
                    {
                        "name": "bom_temperature",
                        "value_template": (
                            "{{ value_json.observations.data[0].air_temp }}"
                        ),
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check that warning was logged with clear indication of the issue
    assert (
        "REST request to http://www.bom.gov.au/fwo/IDN60901/"
        "IDN60901.94767.json returned status 403 with text/html response"
    ) in caplog.text
    assert "Your access is blocked" in caplog.text


async def test_rest_data_warning_on_html_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that warning is logged for error status with HTML content."""
    # Mock a 404 response with HTML error page
    aioclient_mock.get(
        "http://example.com/api",
        status=404,
        text="<html><body><h1>404 Not Found</h1></body></html>",
        headers={"Content-Type": "text/html"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.test }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Should warn for error status with HTML
    assert (
        "REST request to http://example.com/api returned status 404 "
        "with text/html response" in caplog.text
    )
    assert "<html><body><h1>404 Not Found</h1></body></html>" in caplog.text


async def test_rest_data_no_warning_on_json_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test POST request that returns JSON error - no warning expected."""
    aioclient_mock.post(
        "http://example.com/api",
        status=400,
        text='{"error": "Invalid request payload"}',
        headers={"Content-Type": "application/json"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "POST",
                "payload": '{"data": "test"}',
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.error }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Should NOT warn for JSON error responses - users can parse these
    assert (
        "REST request to http://example.com/api returned status 400" not in caplog.text
    )


async def test_rest_data_timeout_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test timeout error logging."""
    aioclient_mock.get(
        "http://example.com/api",
        exc=TimeoutError(),
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "timeout": 10,
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.test }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check timeout error is logged or platform reports not ready
    assert (
        "Timeout while fetching data: http://example.com/api" in caplog.text
        or "Platform rest not ready yet" in caplog.text
    )


async def test_rest_data_boolean_params_converted_to_strings(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that boolean parameters are converted to lowercase strings."""
    # Mock the request and capture the actual URL
    aioclient_mock.get(
        "http://example.com/api",
        status=200,
        json={"status": "ok"},
        headers={"Content-Type": "application/json"},
    )

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "resource": "http://example.com/api",
                "method": "GET",
                "params": {
                    "boolTrue": True,
                    "boolFalse": False,
                    "stringParam": "test",
                    "intParam": 123,
                },
                "sensor": [
                    {
                        "name": "test_sensor",
                        "value_template": "{{ value_json.status }}",
                    }
                ],
            }
        },
    )
    await hass.async_block_till_done()

    # Check that the request was made with boolean values converted to strings
    assert len(aioclient_mock.mock_calls) == 1
    _method, url, _data, _headers = aioclient_mock.mock_calls[0]

    # Check that the URL query parameters have boolean values converted to strings
    assert url.query["boolTrue"] == "true"
    assert url.query["boolFalse"] == "false"
    assert url.query["stringParam"] == "test"
    assert url.query["intParam"] == "123"
