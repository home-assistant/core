"""The tests for the REST binary sensor platform."""

from http import HTTPStatus
import ssl
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant import config as hass_config
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.rest import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    CONTENT_TYPE_JSON,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_missing_basic_config(hass: HomeAssistant) -> None:
    """Test setup with configuration missing required entries."""
    assert await async_setup_component(
        hass, BINARY_SENSOR_DOMAIN, {BINARY_SENSOR_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 0


async def test_setup_missing_config(hass: HomeAssistant) -> None:
    """Test setup with configuration missing required entries."""
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 0


async def test_setup_failed_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection error occurs."""

    aioclient_mock.get("http://localhost", exc=Exception("server offline"))
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 0
    assert "server offline" in caplog.text


async def test_setup_fail_on_ssl_erros(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection error occurs."""
    aioclient_mock.get("https://localhost", exc=ssl.SSLError("ssl error"))
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "https://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 0
    assert "ssl error" in caplog.text


async def test_setup_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup when connection timeout occurs."""
    aioclient_mock.get("http://localhost", exc=TimeoutError())
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 0


async def test_setup_minimum(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with minimum configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1


async def test_setup_minimum_resource_template(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with minimum configuration (resource_template)."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource_template": "{% set url = 'http://localhost' %}{{ url }}",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1


async def test_setup_duplicate_resource_template(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with duplicate resources."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "resource_template": "http://localhost",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 0


async def test_setup_get(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={})
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
                "authentication": "basic",
                "username": "my username",
                "password": "my password",
                "headers": {"Accept": CONTENT_TYPE_JSON},
                "device_class": BinarySensorDeviceClass.PLUG,
            }
        },
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1

    state = hass.states.get("binary_sensor.foo")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.PLUG


async def test_setup_get_template_headers_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=200, json={})
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
                "headers": {
                    "Accept": CONTENT_TYPE_JSON,
                    "User-Agent": "Mozilla/{{ 3 + 2 }}.0",
                },
                "params": {
                    "start": 0,
                    "end": "{{ 3 + 2 }}",
                },
            }
        },
    )
    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    # Verify headers and params were sent correctly by checking the mock was called
    assert aioclient_mock.call_count == 1
    last_request_headers = aioclient_mock.mock_calls[0][3]
    assert last_request_headers["Accept"] == CONTENT_TYPE_JSON
    assert last_request_headers["User-Agent"] == "Mozilla/5.0"


async def test_setup_get_digest_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={})
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
                "authentication": "digest",
                "username": "my username",
                "password": "my password",
                "headers": {"Accept": CONTENT_TYPE_JSON},
            }
        },
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1


async def test_setup_post(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.post("http://localhost", status=HTTPStatus.OK, json={})
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "POST",
                "value_template": "{{ value_json.key }}",
                "payload": '{ "device": "toaster"}',
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
                "authentication": "basic",
                "username": "my username",
                "password": "my password",
                "headers": {"Accept": CONTENT_TYPE_JSON},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1


async def test_setup_get_off(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid off configuration."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/json"},
        json={"dog": False},
    )
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.dog }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1

    state = hass.states.get("binary_sensor.foo")
    assert state.state == STATE_OFF


async def test_setup_get_on(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid on configuration."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/json"},
        json={"dog": True},
    )
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.dog }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1

    state = hass.states.get("binary_sensor.foo")
    assert state.state == STATE_ON


async def test_setup_get_xml(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid xml configuration."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        text="<dog>1</dog>",
    )
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.dog }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1

    state = hass.states.get("binary_sensor.foo")
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("content"),
    [
        (""),
        ("<open></close>"),
    ],
)
async def test_setup_get_bad_xml(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    content: str,
) -> None:
    """Test attributes get extracted from a XML result with bad xml."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        text=content,
    )
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.toplevel.master_value }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1
    state = hass.states.get("binary_sensor.foo")

    assert state.state == STATE_OFF
    assert "REST xml result could not be parsed" in caplog.text


async def test_setup_with_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with exception."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={})
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.dog }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1

    state = hass.states.get("binary_sensor.foo")
    assert state.state == STATE_OFF

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get("http://localhost", exc=aiohttp.ClientError("Request failed"))
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["binary_sensor.foo"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.foo")
    assert state.state == STATE_UNAVAILABLE


async def test_reload(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Verify we can reload reset sensors."""

    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)

    await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "method": "GET",
                "name": "mockrest",
                "resource": "http://localhost",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1

    assert hass.states.get("binary_sensor.mockrest")

    yaml_path = get_fixture_path("configuration.yaml", DOMAIN)
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.mockreset") is None
    assert hass.states.get("binary_sensor.rollout")


async def test_setup_query_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with query params."""
    aioclient_mock.get("http://localhost?search=something", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "params": {"search": "something"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1


async def test_entity_config(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity configuration."""

    config = {
        BINARY_SENSOR_DOMAIN: {
            # REST configuration
            "platform": DOMAIN,
            "method": "GET",
            "resource": "http://localhost",
            # Entity configuration
            "icon": "{{'mdi:one_two_three'}}",
            "picture": "{{'blabla.png'}}",
            "name": "{{'REST' + ' ' + 'Binary Sensor'}}",
            "unique_id": "very_unique",
        },
    }

    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get("binary_sensor.rest_binary_sensor").unique_id
        == "very_unique"
    )

    state = hass.states.get("binary_sensor.rest_binary_sensor")
    assert state.state == "off"
    assert state.attributes == {
        "entity_picture": "blabla.png",
        "friendly_name": "REST Binary Sensor",
        "icon": "mdi:one_two_three",
    }


async def test_availability_in_config(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entity configuration."""

    config = {
        BINARY_SENSOR_DOMAIN: {
            # REST configuration
            "platform": DOMAIN,
            "method": "GET",
            "resource": "http://localhost",
            # Entity configuration
            "availability": "{{value==1}}",
            "name": "{{'REST' + ' ' + 'Binary Sensor'}}",
        },
    }

    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.rest_binary_sensor")
    assert state.state == STATE_UNAVAILABLE


async def test_availability_blocks_value_template(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test availability blocks value_template from rendering."""
    error = "Error parsing value for binary_sensor.block_template: 'x' is undefined"
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, text="51")
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "binary_sensor": [
                        {
                            "unique_id": "block_template",
                            "name": "block_template",
                            "value_template": "{{ x - 1 }}",
                            "availability": "{{ value == '50' }}",
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    assert error not in caplog.text

    state = hass.states.get("binary_sensor.block_template")
    assert state
    assert state.state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, text="50")
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["binary_sensor.block_template"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert error in caplog.text


async def test_setup_get_basic_auth_utf8(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with basic auth using UTF-8 characters including Unicode char \u2018."""
    # Use a password with the Unicode character \u2018 (left single quotation mark)
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={"key": "on"})
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
                "authentication": "basic",
                "username": "test_user",
                "password": "test\u2018password",  # Password with Unicode char
                "headers": {"Accept": CONTENT_TYPE_JSON},
            }
        },
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 1

    state = hass.states.get("binary_sensor.foo")
    assert state.state == STATE_ON
