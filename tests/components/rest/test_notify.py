"""The tests for the rest.notify platform."""

import json
from unittest.mock import patch
import urllib.parse

import respx

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.components.rest import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def setup_notify_component(
    hass: HomeAssistant, platform_name, resource, method, **kwargs
):
    """Set up the notify component."""
    config = {
        notify.DOMAIN: {
            "platform": "rest",
            "name": platform_name,
            "resource": resource,
            "method": method,
            **kwargs,
        }
    }
    assert await async_setup_component(hass, notify.DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, platform_name)


@respx.mock
async def test_reload_notify(hass: HomeAssistant) -> None:
    """Verify we can reload the notify service."""
    respx.get("http://localhost") % 200

    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "resource": "http://127.0.0.1/off",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)

    yaml_path = get_fixture_path("configuration.yaml", "rest")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert not hass.services.has_service(notify.DOMAIN, DOMAIN)
    assert hass.services.has_service(notify.DOMAIN, "rest_reloaded")


@respx.mock
async def test_rest_notify_get(hass: HomeAssistant) -> None:
    """Test sending notification with GET method."""
    respx.get("http://example.com/notify")

    await setup_notify_component(
        hass,
        "rest_test",
        "http://example.com/notify",
        "GET",
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "rest_test",
        {
            "message": "Test message",
        },
        blocking=True,
    )

    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert request.method == "GET"
    assert request.url.params["message"] == "Test message"


@respx.mock
async def test_rest_notify_post_json(hass: HomeAssistant) -> None:
    """Test sending notification with POST_JSON method."""
    respx.post("http://example.com/notify")

    await setup_notify_component(
        hass,
        "rest_test",
        "http://example.com/notify",
        "POST_JSON",
        title_param_name="title",
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "rest_test",
        {
            "message": "Test message",
            "title": "Test title",
        },
        blocking=True,
    )

    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "message": "Test message",
        "title": "Test title",
    }


@respx.mock
async def test_rest_notify_post(hass: HomeAssistant) -> None:
    """Test sending notification with POST method."""
    respx.post("http://example.com/notify")

    await setup_notify_component(
        hass,
        "rest_test",
        "http://example.com/notify",
        "POST",
        title_param_name="title",
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "rest_test",
        {
            "message": "Test message",
            "title": "Test title",
        },
        blocking=True,
    )

    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert "message=Test+message" in request.content.decode()
    assert "title=Test+title" in request.content.decode()


@respx.mock
async def test_rest_notify_multiple_targets_post_json(hass: HomeAssistant) -> None:
    """Test sending notification with multiple targets."""
    respx.post("http://example.com/notify")

    await setup_notify_component(
        hass,
        "rest_test",
        "http://example.com/notify",
        "POST_JSON",
        target_param_name="targets",
        allow_multiple_targets=True,
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "rest_test",
        {
            "message": "Test message",
            "target": ["target1", "target2"],
        },
        blocking=True,
    )

    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "message": "Test message",
        "targets": ["target1", "target2"],
    }


@respx.mock
async def test_rest_notify_multiple_targets_post(hass: HomeAssistant) -> None:
    """Test sending notification with POST method and form data."""
    respx.post("http://example.com/notify")

    await setup_notify_component(
        hass,
        "rest_test_post",
        "http://example.com/notify",
        "POST",
        target_param_name="targets",
        allow_multiple_targets=True,
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "rest_test_post",
        {
            "message": "Test message",
            "target": ["target1", "target2"],
        },
        blocking=True,
    )

    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert urllib.parse.parse_qs(request.content.decode()) == {
        "message": ["Test message"],
        "targets": ["target1", "target2"],
    }


@respx.mock
async def test_rest_notify_multiple_targets_get(hass: HomeAssistant) -> None:
    """Test sending notification with GET method and query parameters."""
    respx.get("http://example.com/notify")

    await setup_notify_component(
        hass,
        "rest_test_get",
        "http://example.com/notify",
        "GET",
        target_param_name="targets",
        allow_multiple_targets=True,
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "rest_test_get",
        {
            "message": "Test message",
            "target": ["target1", "target2"],
        },
        blocking=True,
    )

    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert request.method == "GET"
    assert urllib.parse.parse_qs(request.url.query.decode()) == {
        "message": ["Test message"],
        "targets": ["target1", "target2"],
    }


@respx.mock
async def test_rest_notify_single_target(hass: HomeAssistant) -> None:
    """Test sending notification with single target when multiple targets not allowed."""
    respx.post("http://example.com/notify")

    await setup_notify_component(
        hass,
        "rest_test",
        "http://example.com/notify",
        "POST_JSON",
        target_param_name="target",
        allow_multiple_targets=False,
    )

    await hass.services.async_call(
        notify.DOMAIN,
        "rest_test",
        {
            "message": "Test message",
            "target": ["target1", "target2"],  # Only first target should be used
        },
        blocking=True,
    )

    assert len(respx.calls) == 1
    request = respx.calls[0].request
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "message": "Test message",
        "target": "target1",
    }
