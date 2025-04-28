"""The tests for the REST sensor platform."""

from http import HTTPStatus
import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

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


@respx.mock
async def test_setup_failed_connect(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup when connection error occurs."""
    respx.get("http://localhost").mock(
        side_effect=httpx.RequestError("server offline", request=MagicMock())
    )
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


@respx.mock
async def test_setup_fail_on_ssl_erros(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup when connection error occurs."""
    respx.get("https://localhost").mock(side_effect=ssl.SSLError("ssl error"))
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


@respx.mock
async def test_setup_timeout(hass: HomeAssistant) -> None:
    """Test setup when connection timeout occurs."""
    respx.get("http://localhost").mock(side_effect=TimeoutError())
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": DOMAIN, "resource": "localhost", "method": "GET"}},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0


@respx.mock
async def test_setup_minimum(hass: HomeAssistant) -> None:
    """Test setup with minimum configuration."""
    respx.get("http://localhost") % HTTPStatus.OK
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


@respx.mock
async def test_setup_encoding(hass: HomeAssistant) -> None:
    """Test setup with non-utf8 encoding."""
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        stream=httpx.ByteStream("tack själv".encode(encoding="iso-8859-1")),
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
    assert hass.states.get("sensor.mysensor").state == "tack själv"


@respx.mock
@pytest.mark.parametrize(
    ("ssl_cipher_list", "ssl_cipher_list_expected"),
    [
        ("python_default", SSLCipherList.PYTHON_DEFAULT),
        ("intermediate", SSLCipherList.INTERMEDIATE),
        ("modern", SSLCipherList.MODERN),
    ],
)
async def test_setup_ssl_ciphers(
    hass: HomeAssistant, ssl_cipher_list: str, ssl_cipher_list_expected: SSLCipherList
) -> None:
    """Test setup with minimum configuration."""
    with patch(
        "homeassistant.components.rest.data.create_async_httpx_client",
        return_value=MagicMock(request=AsyncMock(return_value=respx.MockResponse())),
    ) as httpx:
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
        httpx.assert_called_once_with(
            hass,
            verify_ssl=True,
            default_encoding="UTF-8",
            ssl_cipher_list=ssl_cipher_list_expected,
        )


@respx.mock
async def test_manual_update(hass: HomeAssistant) -> None:
    """Test setup with minimum configuration."""
    await async_setup_component(hass, "homeassistant", {})
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"data": "first"}
    )
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

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"data": "second"}
    )
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.mysensor"]},
        blocking=True,
    )
    assert hass.states.get("sensor.mysensor").state == "second"


@respx.mock
async def test_setup_minimum_resource_template(hass: HomeAssistant) -> None:
    """Test setup with minimum configuration (resource_template)."""
    respx.get("http://localhost") % HTTPStatus.OK
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


@respx.mock
async def test_setup_duplicate_resource_template(hass: HomeAssistant) -> None:
    """Test setup with duplicate resources."""
    respx.get("http://localhost") % HTTPStatus.OK
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


@respx.mock
async def test_setup_get(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"key": "123"}
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


@respx.mock
async def test_setup_timestamp(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with valid configuration."""
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"key": "2021-11-11 11:39Z"}
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
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"key": "invalid time stamp"}
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
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"key": "2021-10-11 11:39"}
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


@respx.mock
async def test_setup_get_templated_headers_params(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    respx.get("http://localhost").respond(status_code=200, json={})
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

    assert respx.calls.last.request.headers["Accept"] == CONTENT_TYPE_JSON
    assert respx.calls.last.request.headers["User-Agent"] == "Mozilla/5.0"
    assert respx.calls.last.request.url.query == b"start=0&end=5"


@respx.mock
async def test_setup_get_digest_auth(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"key": "123"}
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


@respx.mock
async def test_setup_post(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    respx.post("http://localhost").respond(
        status_code=HTTPStatus.OK, json={"key": "123"}
    )
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


@respx.mock
async def test_setup_get_xml(hass: HomeAssistant) -> None:
    """Test setup with valid xml configuration."""
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        content="<dog>123</dog>",
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


@respx.mock
async def test_setup_query_params(hass: HomeAssistant) -> None:
    """Test setup with query params."""
    respx.get("http://localhost", params={"search": "something"}) % HTTPStatus.OK
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


@respx.mock
async def test_update_with_json_attrs(hass: HomeAssistant) -> None:
    """Test attributes get extracted from a JSON result."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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


@respx.mock
async def test_update_with_no_template(hass: HomeAssistant) -> None:
    """Test update when there is no value template."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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


@respx.mock
async def test_update_with_json_attrs_no_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test attributes when no JSON result fetched."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": CONTENT_TYPE_JSON},
        content="",
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


@respx.mock
async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test attributes get extracted from a JSON result."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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


@respx.mock
async def test_update_with_json_attrs_bad_JSON(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test attributes get extracted from a JSON result."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": CONTENT_TYPE_JSON},
        content="This is text rather than JSON data.",
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


@respx.mock
async def test_update_with_json_attrs_with_json_attrs_path(hass: HomeAssistant) -> None:
    """Test attributes get extracted from a JSON result with a template for the attributes."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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


@respx.mock
async def test_update_with_xml_convert_json_attrs_with_json_attrs_path(
    hass: HomeAssistant,
) -> None:
    """Test attributes get extracted from a JSON result that was converted from XML with a template for the attributes."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        content="<toplevel><master_value>123</master_value><second_level><some_json_key>some_json_value</some_json_key><some_json_key2>some_json_value2</some_json_key2></second_level></toplevel>",
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


@respx.mock
async def test_update_with_xml_convert_json_attrs_with_jsonattr_template(
    hass: HomeAssistant,
) -> None:
    """Test attributes get extracted from a JSON result that was converted from XML."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        content='<?xml version="1.0" encoding="utf-8"?><response><scan>0</scan><ver>12556</ver><count>48</count><ssid>alexander</ssid><bss><valid>0</valid><name>0</name><privacy>0</privacy><wlan>123</wlan><strength>0</strength></bss><led0>0</led0><led1>0</led1><led2>0</led2><led3>0</led3><led4>0</led4><led5>0</led5><led6>0</led6><led7>0</led7><btn0>up</btn0><btn1>up</btn1><btn2>up</btn2><btn3>up</btn3><pot0>0</pot0><usr0>0</usr0><temp0>0x0XF0x0XF</temp0><time0> 0</time0></response>',
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


@respx.mock
async def test_update_with_application_xml_convert_json_attrs_with_jsonattr_template(
    hass: HomeAssistant,
) -> None:
    """Test attributes get extracted from a JSON result that was converted from XML with application/xml mime type."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": "application/xml"},
        content="<main><dog>1</dog><cat>3</cat></main>",
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


@respx.mock
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
) -> None:
    """Test attributes get extracted from a XML result with bad xml."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        content=content,
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


@respx.mock
async def test_update_with_failed_get(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test attributes get extracted from a XML result with bad xml."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        headers={"content-type": "text/xml"},
        content="",
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


@respx.mock
async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload reset sensors."""

    respx.get("http://localhost") % HTTPStatus.OK

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


@respx.mock
async def test_entity_config(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
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

    respx.get("http://localhost").respond(status_code=HTTPStatus.OK, text="123")
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


@respx.mock
async def test_availability_in_config(hass: HomeAssistant) -> None:
    """Test entity configuration."""
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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


@respx.mock
async def test_json_response_with_availability_syntax_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test availability with syntax error."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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


@respx.mock
async def test_json_response_with_availability(hass: HomeAssistant) -> None:
    """Test availability with complex json."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
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


@respx.mock
async def test_availability_blocks_value_template(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test availability blocks value_template from rendering."""
    error = "Error parsing value for sensor.block_template: 'x' is undefined"
    respx.get("http://localhost").respond(status_code=HTTPStatus.OK, content="51")
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

    respx.clear()
    respx.get("http://localhost").respond(status_code=HTTPStatus.OK, content="50")
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.block_template"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert error in caplog.text
