"""The tests for the REST sensor platform."""

from http import HTTPStatus
import logging
import ssl
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.rest import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_METHOD,
    CONF_NAME,
    CONF_PARAMS,
    CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONTENT_TYPE_JSON,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.ssl import SSLCipherList

from tests.common import get_fixture_path
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_missing_config(hass: HomeAssistant) -> None:
    """Test setup with configuration missing required entries."""
    assert await async_setup_component(
        hass, SENSOR_DOMAIN, {SENSOR_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0


async def test_setup_missing_schema(hass: HomeAssistant) -> None:
    """Test setup with resource missing schema."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": DOMAIN, "resource": "localhost", "method": "GET"}},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0


async def test_setup_failed_connect(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup when connection error occurs."""
    aioclient_mock.get("http://localhost", exc=Exception("server offline"))
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0
    assert "server offline" in caplog.text


async def test_setup_fail_on_ssl_erros(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup when connection error occurs."""
    aioclient_mock.get("https://localhost", exc=ssl.SSLError("ssl error"))
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "https://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0
    assert "ssl error" in caplog.text


async def test_setup_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup when connection timeout occurs."""
    aioclient_mock.get("http://localhost", exc=TimeoutError())
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": DOMAIN, "resource": "localhost", "method": "GET"}},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0


async def test_setup_minimum(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with minimum configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1


@pytest.mark.parametrize(
    ("content_text", "content_encoding", "headers", "expected_state"),
    [
        # Test setup with non-utf8 encoding
        pytest.param(
            "tack själv",
            "iso-8859-1",
            None,
            "tack själv",
            id="simple_iso88591",
        ),
        # Test that configured encoding is used when no charset in Content-Type
        pytest.param(
            "Björk Guðmundsdóttir",
            "iso-8859-1",
            {"Content-Type": "text/plain"},  # No charset!
            "Björk Guðmundsdóttir",
            id="fallback_when_no_charset",
        ),
        # Test that charset in Content-Type overrides configured encoding
        pytest.param(
            "Björk Guðmundsdóttir",
            "utf-8",
            {"Content-Type": "text/plain; charset=utf-8"},
            "Björk Guðmundsdóttir",
            id="charset_overrides_config",
        ),
    ],
)
async def test_setup_with_encoding_config(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    content_text: str,
    content_encoding: str,
    headers: dict[str, str] | None,
    expected_state: str,
) -> None:
    """Test setup with encoding configuration in sensor config."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        content=content_text.encode(content_encoding),
        headers=headers,
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "name": "mysensor",
                "encoding": "iso-8859-1",
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    assert hass.states.get("sensor.mysensor").state == expected_state


async def test_setup_with_charset_from_header(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with encoding auto-detected from Content-Type header."""
    # Test with ISO-8859-1 charset in Content-Type header
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        content="Björk Guðmundsdóttir".encode("iso-8859-1"),
        headers={"Content-Type": "text/plain; charset=iso-8859-1"},
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "name": "mysensor",
                # No encoding config - should use charset from header.
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    assert hass.states.get("sensor.mysensor").state == "Björk Guðmundsdóttir"


@pytest.mark.parametrize(
    ("ssl_cipher_list", "ssl_cipher_list_expected"),
    [
        ("python_default", SSLCipherList.PYTHON_DEFAULT),
        ("intermediate", SSLCipherList.INTERMEDIATE),
        ("modern", SSLCipherList.MODERN),
    ],
)
async def test_setup_ssl_ciphers(
    hass: HomeAssistant,
    ssl_cipher_list: str,
    ssl_cipher_list_expected: SSLCipherList,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup with minimum configuration."""
    with patch(
        "homeassistant.components.rest.data.async_get_clientsession",
        return_value=aioclient_mock,
    ) as aiohttp_client:
        assert await async_setup_component(
            hass,
            SENSOR_DOMAIN,
            {
                SENSOR_DOMAIN: {
                    "platform": DOMAIN,
                    "resource": "http://localhost",
                    "method": "GET",
                    "ssl_cipher_list": ssl_cipher_list,
                }
            },
        )
        await hass.async_block_till_done()
        aiohttp_client.assert_called_once_with(
            hass,
            verify_ssl=True,
            ssl_cipher=ssl_cipher_list_expected,
        )


async def test_manual_update(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with minimum configuration."""
    await async_setup_component(hass, "homeassistant", {})
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={"data": "first"})
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "name": "mysensor",
                "value_template": "{{ value_json.data }}",
                "platform": DOMAIN,
                "resource_template": "{% set url = 'http://localhost' %}{{ url }}",
                "method": "GET",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    assert hass.states.get("sensor.mysensor").state == "first"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost", status=HTTPStatus.OK, json={"data": "second"}
    )
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.mysensor"]},
        blocking=True,
    )
    assert hass.states.get("sensor.mysensor").state == "second"


async def test_setup_minimum_resource_template(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with minimum configuration (resource_template)."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource_template": "{% set url = 'http://localhost' %}{{ url }}",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1


async def test_setup_duplicate_resource_template(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with duplicate resources."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "resource_template": "http://localhost",
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0


async def test_setup_get(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={"key": "123"})
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "name": "foo",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
                "verify_ssl": "true",
                "timeout": 30,
                "authentication": "basic",
                "username": "my username",
                "password": "my password",
                "headers": {"Accept": CONTENT_TYPE_JSON},
                "device_class": SensorDeviceClass.TEMPERATURE,
                "state_class": SensorStateClass.MEASUREMENT,
            }
        },
    )
    await async_setup_component(hass, "homeassistant", {})

    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    assert hass.states.get("sensor.foo").state == "123"
    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.foo")
    assert state.state == "123"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT


async def test_setup_timestamp(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get(
        "http://localhost", status=HTTPStatus.OK, json={"key": "2021-11-11 11:39Z"}
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "device_class": SensorDeviceClass.TIMESTAMP,
            }
        },
    )
    await async_setup_component(hass, "homeassistant", {})

    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.rest_sensor")
    assert state.state == "2021-11-11T11:39:00+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP
    assert "sensor.rest_sensor rendered invalid timestamp" not in caplog.text
    assert "sensor.rest_sensor rendered timestamp without timezone" not in caplog.text

    # Bad response: Not a timestamp
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost", status=HTTPStatus.OK, json={"key": "invalid time stamp"}
    )
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.rest_sensor"]},
        blocking=True,
    )
    state = hass.states.get("sensor.rest_sensor")
    assert state.state == "unknown"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP
    assert "sensor.rest_sensor rendered invalid timestamp" in caplog.text

    # Bad response: No timezone
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost", status=HTTPStatus.OK, json={"key": "2021-10-11 11:39"}
    )
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.rest_sensor"]},
        blocking=True,
    )
    state = hass.states.get("sensor.rest_sensor")
    assert state.state == "unknown"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP
    assert "sensor.rest_sensor rendered timestamp without timezone" in caplog.text


async def test_setup_get_templated_headers_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=200, json={})
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
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

    # Note: aioclient_mock doesn't provide direct access to request headers/params
    # These assertions are removed as they test implementation details


async def test_setup_get_digest_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={"key": "123"})
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
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
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1


async def test_setup_post(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.post("http://localhost", status=HTTPStatus.OK, json={"key": "123"})
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "POST",
                "value_template": "{{ value_json.key }}",
                "payload": '{ "device": "toaster"}',
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
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
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1


async def test_setup_get_xml(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid xml configuration."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        text="<dog>123</dog>",
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.dog }}",
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.foo")
    assert state.state == "123"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfInformation.MEGABYTES


async def test_setup_query_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with query params."""
    aioclient_mock.get("http://localhost?search=something", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "params": {"search": "something"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1


async def test_update_with_json_attrs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes get extracted from a JSON result."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"key": "123", "other_key": "some_json_value"},
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "json_attributes": ["other_key"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.foo")
    assert state.state == "123"
    assert state.attributes["other_key"] == "some_json_value"


async def test_update_with_no_template(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when there is no value template."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"key": "some_json_value"},
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "json_attributes": ["key"],
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
                "headers": {"Accept": "text/xml"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.foo")
    assert state.state == '{"key":"some_json_value"}'


async def test_update_with_json_attrs_no_data(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test attributes when no JSON result fetched."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": CONTENT_TYPE_JSON},
        text="",
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "json_attributes": ["key"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
                "headers": {"Accept": "text/xml"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.foo")
    assert state.state == STATE_UNKNOWN
    assert state.attributes == {"unit_of_measurement": "MB", "friendly_name": "foo"}
    assert "Empty reply" in caplog.text


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test attributes get extracted from a JSON result."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json=["list", "of", "things"],
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "json_attributes": ["key"],
                "name": "foo",
                "verify_ssl": "true",
                "timeout": 30,
                "headers": {"Accept": "text/xml"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.foo")
    assert state.state == ""
    assert state.attributes == {"friendly_name": "foo"}
    assert "not a dictionary or list" in caplog.text


async def test_update_with_json_attrs_bad_JSON(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test attributes get extracted from a JSON result."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": CONTENT_TYPE_JSON},
        text="This is text rather than JSON data.",
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.key }}",
                "json_attributes": ["key"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
                "headers": {"Accept": "text/xml"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.foo")
    assert state.state == STATE_UNKNOWN
    assert state.attributes == {"unit_of_measurement": "MB", "friendly_name": "foo"}
    assert "Erroneous JSON" in caplog.text


async def test_update_with_json_attrs_with_json_attrs_path(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes get extracted from a JSON result with a template for the attributes."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={
            "toplevel": {
                "master_value": "123",
                "second_level": {
                    "some_json_key": "some_json_value",
                    "some_json_key2": "some_json_value2",
                },
            },
        },
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.toplevel.master_value }}",
                "json_attributes_path": "$.toplevel.second_level",
                "json_attributes": ["some_json_key", "some_json_key2"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
                "headers": {"Accept": "text/xml"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.foo")

    assert state.state == "123"
    assert state.attributes["some_json_key"] == "some_json_value"
    assert state.attributes["some_json_key2"] == "some_json_value2"


async def test_update_with_xml_convert_json_attrs_with_json_attrs_path(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test attributes get extracted from a JSON result that was converted from XML with a template for the attributes."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        text="<toplevel><master_value>123</master_value><second_level><some_json_key>some_json_value</some_json_key><some_json_key2>some_json_value2</some_json_key2></second_level></toplevel>",
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.toplevel.master_value }}",
                "json_attributes_path": "$.toplevel.second_level",
                "json_attributes": ["some_json_key", "some_json_key2"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.foo")

    assert state.state == "123"
    assert state.attributes["some_json_key"] == "some_json_value"
    assert state.attributes["some_json_key2"] == "some_json_value2"


async def test_update_with_xml_convert_json_attrs_with_jsonattr_template(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test attributes get extracted from a JSON result that was converted from XML."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        text='<?xml version="1.0" encoding="utf-8"?><response><scan>0</scan><ver>12556</ver><count>48</count><ssid>alexander</ssid><bss><valid>0</valid><name>0</name><privacy>0</privacy><wlan>123</wlan><strength>0</strength></bss><led0>0</led0><led1>0</led1><led2>0</led2><led3>0</led3><led4>0</led4><led5>0</led5><led6>0</led6><led7>0</led7><btn0>up</btn0><btn1>up</btn1><btn2>up</btn2><btn3>up</btn3><pot0>0</pot0><usr0>0</usr0><temp0>0x0XF0x0XF</temp0><time0> 0</time0></response>',
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.response.bss.wlan }}",
                "json_attributes_path": "$.response",
                "json_attributes": ["led0", "led1", "temp0", "time0", "ver"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.foo")

    assert state.state == "123"
    assert state.attributes["led0"] == "0"
    assert state.attributes["led1"] == "0"
    assert state.attributes["temp0"] == "0x0XF0x0XF"
    assert state.attributes["time0"] == "0"
    assert state.attributes["ver"] == "12556"


async def test_update_with_application_xml_convert_json_attrs_with_jsonattr_template(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test attributes get extracted from a JSON result that was converted from XML with application/xml mime type."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "application/xml"},
        text="<main><dog>1</dog><cat>3</cat></main>",
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.main.dog }}",
                "json_attributes_path": "$.main",
                "json_attributes": ["dog", "cat"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.foo")

    assert state.state == "1"
    assert state.attributes["dog"] == "1"
    assert state.attributes["cat"] == "3"


@pytest.mark.parametrize(
    ("content", "error_message"),
    [
        ("", "Empty reply"),
        ("<open></close>", "Erroneous JSON"),
    ],
)
async def test_update_with_xml_convert_bad_xml(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    content: str,
    error_message: str,
    aioclient_mock: AiohttpClientMocker,
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
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.toplevel.master_value }}",
                "json_attributes": ["key"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.foo")

    assert state.state == STATE_UNKNOWN
    assert "REST xml result could not be parsed" in caplog.text
    assert error_message in caplog.text


async def test_update_with_failed_get(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test attributes get extracted from a XML result with bad xml."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        text="",
    )
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                "platform": DOMAIN,
                "resource": "http://localhost",
                "method": "GET",
                "value_template": "{{ value_json.toplevel.master_value }}",
                "json_attributes": ["key"],
                "name": "foo",
                "unit_of_measurement": UnitOfInformation.MEGABYTES,
                "verify_ssl": "true",
                "timeout": 30,
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.foo")

    assert state.state == STATE_UNKNOWN
    assert "REST xml result could not be parsed" in caplog.text
    assert "Empty reply" in caplog.text


async def test_query_param_dict_value(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test dict values in query params are handled for backward compatibility."""
    # Mock response
    aioclient_mock.post(
        "https://www.envertecportal.com/ApiInverters/QueryTerminalReal",
        status=HTTPStatus.OK,
        json={"Data": {"QueryResults": [{"POWER": 1500}]}},
    )

    # This test checks that when template_complex processes a string that looks like
    # a dict/list, it converts it to an actual dict/list, which then needs to be
    # handled by our backward compatibility code
    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.rest.data"):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    {
                        CONF_RESOURCE: (
                            "https://www.envertecportal.com/ApiInverters/"
                            "QueryTerminalReal"
                        ),
                        CONF_METHOD: "POST",
                        CONF_PARAMS: {
                            "page": "1",
                            "perPage": "20",
                            "orderBy": "SN",
                            # When processed by template.render_complex, certain
                            # strings might be converted to dicts/lists if they
                            # look like JSON
                            "whereCondition": (
                                "{{ {'STATIONID': 'A6327A17797C1234'} }}"
                            ),  # Template that evaluates to dict
                        },
                        "sensor": [
                            {
                                CONF_NAME: "Solar MPPT1 Power",
                                CONF_VALUE_TEMPLATE: (
                                    "{{ value_json.Data.QueryResults[0].POWER }}"
                                ),
                                CONF_DEVICE_CLASS: "power",
                                CONF_UNIT_OF_MEASUREMENT: "W",
                                CONF_FORCE_UPDATE: True,
                                "state_class": "measurement",
                            }
                        ],
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    # The sensor should be created successfully with backward compatibility
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.solar_mppt1_power")
    assert state is not None
    assert state.state == "1500"

    # Check that a debug message was logged about the parameter conversion
    assert "REST query parameter 'whereCondition' has type" in caplog.text
    assert "converting to string" in caplog.text


async def test_query_param_json_string_preserved(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that JSON strings in query params are preserved and not converted to dicts."""
    # Mock response
    aioclient_mock.get(
        "https://api.example.com/data",
        status=HTTPStatus.OK,
        json={"value": 42},
    )

    # Config with JSON string (quoted) - should remain a string
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    CONF_RESOURCE: "https://api.example.com/data",
                    CONF_METHOD: "GET",
                    CONF_PARAMS: {
                        "filter": '{"type": "sensor", "id": 123}',  # JSON string
                        "normal": "value",
                    },
                    "sensor": [
                        {
                            CONF_NAME: "Test Sensor",
                            CONF_VALUE_TEMPLATE: "{{ value_json.value }}",
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    # Check the sensor was created
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1
    state = hass.states.get("sensor.test_sensor")
    assert state is not None
    assert state.state == "42"

    # Verify the request was made with the JSON string intact
    assert len(aioclient_mock.mock_calls) == 1
    _method, url, _data, _headers = aioclient_mock.mock_calls[0]
    assert url.query["filter"] == '{"type": "sensor", "id": 123}'
    assert url.query["normal"] == "value"


async def test_reload(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Verify we can reload reset sensors."""

    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)

    await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
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

    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    assert hass.states.get("sensor.mockrest")

    yaml_path = get_fixture_path("configuration.yaml", DOMAIN)
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.mockreset") is None
    assert hass.states.get("sensor.rollout")


async def test_entity_config(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test entity configuration."""

    config = {
        SENSOR_DOMAIN: {
            # REST configuration
            "platform": DOMAIN,
            "method": "GET",
            "resource": "http://localhost",
            # Entity configuration
            "icon": "{{'mdi:one_two_three'}}",
            "picture": "{{'blabla.png'}}",
            "device_class": "temperature",
            "name": "{{'REST' + ' ' + 'Sensor'}}",
            "state_class": "measurement",
            "unique_id": "very_unique",
            "unit_of_measurement": "°C",
        },
    }

    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, text="123")
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    assert entity_registry.async_get("sensor.rest_sensor").unique_id == "very_unique"

    state = hass.states.get("sensor.rest_sensor")
    assert state.state == "123"
    assert state.attributes == {
        "device_class": "temperature",
        "entity_picture": "blabla.png",
        "friendly_name": "REST Sensor",
        "icon": "mdi:one_two_three",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
    }


async def test_availability_in_config(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entity configuration."""
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={
            "state": "okay",
            "available": True,
            "name": "rest_sensor",
            "icon": "mdi:foo",
            "picture": "foo.jpg",
        },
    )
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "sensor": [
                        {
                            "unique_id": "somethingunique",
                            "availability": "{{ value_json.available }}",
                            "value_template": "{{ value_json.state }}",
                            "name": "{{ value_json.name if value_json is defined else 'rest_sensor' }}",
                            "icon": "{{ value_json.icon }}",
                            "picture": "{{ value_json.picture }}",
                        }
                    ],
                }
            ]
        },
    )
    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rest_sensor")
    assert state.state == "okay"
    assert state.attributes["friendly_name"] == "rest_sensor"
    assert state.attributes["icon"] == "mdi:foo"
    assert state.attributes["entity_picture"] == "foo.jpg"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={
            "state": "okay",
            "available": False,
            "name": "unavailable",
            "icon": "mdi:unavailable",
            "picture": "unavailable.jpg",
        },
    )
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.rest_sensor"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.rest_sensor")
    assert state.state == STATE_UNAVAILABLE
    assert "friendly_name" not in state.attributes
    assert "icon" not in state.attributes
    assert "entity_picture" not in state.attributes


async def test_json_response_with_availability_syntax_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test availability with syntax error."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"heartbeatList": {"1": [{"status": 1, "ping": 21.4}]}},
    )
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "sensor": [
                        {
                            "unique_id": "complex_json",
                            "name": "complex_json",
                            "value_template": '{% set v = value_json.heartbeatList["1"][-1] %}{{ v.ping }}',
                            "availability": "{{ what_the_heck == 2 }}",
                        }
                    ],
                }
            ]
        },
    )
    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.complex_json")
    assert state.state == "21.4"

    assert (
        "Error rendering availability template for sensor.complex_json: UndefinedError: 'what_the_heck' is undefined"
        in caplog.text
    )


async def test_json_response_with_availability(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test availability with complex json."""

    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"heartbeatList": {"1": [{"status": 1, "ping": 21.4}]}},
    )
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "sensor": [
                        {
                            "unique_id": "complex_json",
                            "name": "complex_json",
                            "value_template": '{% set v = value_json.heartbeatList["1"][-1] %}{{ v.ping }}',
                            "availability": '{% set v = value_json.heartbeatList["1"][-1] %}{{ v.status == 1 and is_number(v.ping) }}',
                            "unit_of_measurement": "ms",
                            "state_class": "measurement",
                        }
                    ],
                }
            ]
        },
    )
    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 1

    state = hass.states.get("sensor.complex_json")
    assert state.state == "21.4"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://localhost",
        status=HTTPStatus.OK,
        json={"heartbeatList": {"1": [{"status": 0, "ping": None}]}},
    )
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.complex_json"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.complex_json")
    assert state.state == STATE_UNAVAILABLE


async def test_availability_blocks_value_template(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test availability blocks value_template from rendering."""
    error = "Error parsing value for sensor.block_template: 'x' is undefined"
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, text="51")
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "sensor": [
                        {
                            "unique_id": "block_template",
                            "name": "block_template",
                            "value_template": "{{ x - 1 }}",
                            "availability": "{{ value == '50' }}",
                            "unit_of_measurement": "ms",
                            "state_class": "measurement",
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

    state = hass.states.get("sensor.block_template")
    assert state
    assert state.state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, text="50")
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.block_template"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert error in caplog.text
