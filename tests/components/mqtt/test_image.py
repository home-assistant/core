"""The tests for mqtt image component."""

from base64 import b64encode
from http import HTTPStatus
import json
import ssl
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from homeassistant.components import image, mqtt
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .test_common import (
    help_custom_config,
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_discovery_update_unchanged,
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_reloadable,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_skipped_async_ha_write_state,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.typing import (
    ClientSessionGenerator,
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
)

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {image.DOMAIN: {"name": "test", "image_topic": "test_topic"}}
}


@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [{mqtt.DOMAIN: {image.DOMAIN: {"image_topic": "test/image", "name": "Test"}}}],
)
async def test_run_image_setup(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test that it fetches the given payload."""
    topic = "test/image"
    await mqtt_mock_entry()

    state = hass.states.get("image.test")
    assert state.state == STATE_UNKNOWN
    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.test?token={access_token}",
        "friendly_name": "Test",
    }

    async_fire_mqtt_message(hass, topic, b"grass")
    client = await hass_client_no_auth()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"grass"

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00"


@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                image.DOMAIN: {
                    "image_topic": "test/image",
                    "name": "Test",
                    "image_encoding": "b64",
                    "content_type": "image/png",
                }
            }
        }
    ],
)
async def test_run_image_b64_encoded(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that it fetches the given encoded payload."""
    topic = "test/image"
    await mqtt_mock_entry()

    state = hass.states.get("image.test")
    assert state.state == STATE_UNKNOWN
    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.test?token={access_token}",
        "friendly_name": "Test",
    }

    # Fire incorrect encoded message (utf-8 encoded string)
    async_fire_mqtt_message(hass, topic, "grass")
    client = await hass_client_no_auth()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Error processing image data received at topic test/image" in caplog.text

    # Fire correctly encoded message (b64 encoded payload)
    async_fire_mqtt_message(hass, topic, b64encode(b"grass"))
    client = await hass_client_no_auth()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"grass"

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00"


@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                "image": {
                    "image_topic": "test/image",
                    "name": "Test",
                    "encoding": "utf-8",
                    "image_encoding": "b64",
                    "availability": {"topic": "test/image_availability"},
                }
            }
        }
    ],
)
async def test_image_b64_encoded_with_availability(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test availability works if b64 encoding is turned on."""
    topic = "test/image"
    topic_availability = "test/image_availability"
    await mqtt_mock_entry()

    state = hass.states.get("image.test")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Make sure we are available
    async_fire_mqtt_message(hass, topic_availability, "online")

    state = hass.states.get("image.test")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    url = hass.states.get("image.test").attributes["entity_picture"]

    async_fire_mqtt_message(hass, topic, b64encode(b"grass"))

    client = await hass_client_no_auth()
    resp = await client.get(url)
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "grass"

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00"


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                "image": {
                    "url_topic": "test/image",
                    "name": "Test",
                }
            }
        }
    ],
)
async def test_image_from_url(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup with URL."""
    respx.get("http://localhost/test.png").respond(
        status_code=HTTPStatus.OK, content_type="image/png", content=b"milk"
    )
    topic = "test/image"

    await mqtt_mock_entry()

    # Test first with invalid URL
    async_fire_mqtt_message(hass, topic, b"/tmp/test.png")
    await hass.async_block_till_done()

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00"

    assert "Invalid image URL" in caplog.text

    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.test?token={access_token}",
        "friendly_name": "Test",
    }

    async_fire_mqtt_message(hass, topic, b"http://localhost/test.png")

    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "milk"
    assert respx.get("http://localhost/test.png").call_count == 1

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00"

    # Check the image is not refetched
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "milk"
    assert respx.get("http://localhost/test.png").call_count == 1

    # Check the image is refetched when receiving a new message on the URL topic
    respx.get("http://localhost/test.png").respond(
        status_code=HTTPStatus.OK, content_type="image/png", content=b"milk"
    )
    async_fire_mqtt_message(hass, topic, b"http://localhost/test.png")

    await hass.async_block_till_done()

    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "milk"
    assert respx.get("http://localhost/test.png").call_count == 2


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                "image": {
                    "url_topic": "test/image",
                    "name": "Test",
                    "url_template": "{{ value_json.val }}",
                }
            }
        }
    ],
)
async def test_image_from_url_with_template(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test setup with URL."""
    respx.get("http://localhost/test.png").respond(
        status_code=HTTPStatus.OK, content_type="image/png", content=b"milk"
    )
    topic = "test/image"

    await mqtt_mock_entry()

    state = hass.states.get("image.test")
    assert state.state == STATE_UNKNOWN

    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.test?token={access_token}",
        "friendly_name": "Test",
    }

    async_fire_mqtt_message(hass, topic, '{"val": "http://localhost/test.png"}')

    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "milk"

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00"


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                "image": {
                    "url_topic": "test/image",
                    "name": "Test",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("content_type", "setup_ok"),
    [
        ("image/jpg", True),
        ("image", True),
        ("image/png", True),
        ("text/javascript", False),
    ],
)
async def test_image_from_url_content_type(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    content_type: str,
    setup_ok: bool,
) -> None:
    """Test setup with URL."""
    respx.get("http://localhost/test.png").respond(
        status_code=HTTPStatus.OK, content_type=content_type, content=b"milk"
    )
    topic = "test/image"

    await mqtt_mock_entry()

    # Test first with invalid URL
    async_fire_mqtt_message(hass, topic, b"/tmp/test.png")
    await hass.async_block_till_done()

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00"

    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.test?token={access_token}",
        "friendly_name": "Test",
    }

    async_fire_mqtt_message(hass, topic, b"http://localhost/test.png")

    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK if setup_ok else HTTPStatus.SERVICE_UNAVAILABLE
    if setup_ok:
        body = await resp.text()
        assert body == "milk"

    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00+00:00" if setup_ok else STATE_UNKNOWN


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                "image": {
                    "url_topic": "test/image",
                    "name": "Test",
                    "encoding": "utf-8",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    "side_effect",
    [
        httpx.RequestError("server offline", request=MagicMock()),
        httpx.TimeoutException,
        ssl.SSLError,
    ],
)
async def test_image_from_url_fails(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    side_effect: Exception,
) -> None:
    """Test setup with minimum configuration."""
    respx.get("http://localhost/test.png").mock(side_effect=side_effect)
    topic = "test/image"

    await mqtt_mock_entry()

    state = hass.states.get("image.test")
    assert state.state == STATE_UNKNOWN
    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.test?token={access_token}",
        "friendly_name": "Test",
    }

    async_fire_mqtt_message(hass, topic, b"http://localhost/test.png")

    await hass.async_block_till_done()

    state = hass.states.get("image.test")

    # The image failed to load, the last image update is registered
    # but _last_image was set to `None`
    assert state.state == "2023-04-01T00:00:00+00:00"
    client = await hass_client_no_auth()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


@respx.mock
@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
@pytest.mark.parametrize(
    ("hass_config", "error_msg"),
    [
        (
            {
                mqtt.DOMAIN: {
                    "image": {
                        "url_topic": "test/image",
                        "content_type": "image/jpg",
                        "name": "Test",
                        "encoding": "utf-8",
                    }
                }
            },
            "Option `content_type` can not be used together with `url_topic`",
        ),
        (
            {
                mqtt.DOMAIN: {
                    "image": {
                        "url_topic": "test/image",
                        "image_topic": "test/image-data-topic",
                        "name": "Test",
                        "encoding": "utf-8",
                    }
                }
            },
            "two or more values in the same group of exclusion 'image_topic'",
        ),
        (
            {
                mqtt.DOMAIN: {
                    "image": {
                        "name": "Test",
                        "encoding": "utf-8",
                    }
                }
            },
            "Expected one of [`image_topic`, `url_topic`], got none",
        ),
    ],
)
@pytest.mark.usefixtures("hass", "hass_client_no_auth")
async def test_image_config_fails(
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    error_msg: str,
) -> None:
    """Test setup with minimum configuration."""
    assert await mqtt_mock_entry()
    assert error_msg in caplog.text


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, image.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                image.DOMAIN: [
                    {
                        "name": "Test 1",
                        "image_topic": "test-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "image_topic": "test-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                ]
            }
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one image per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, image.DOMAIN)


async def test_discovery_removal_image(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered image."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][image.DOMAIN])
    await help_test_discovery_removal(hass, mqtt_mock_entry, image.DOMAIN, data)


async def test_discovery_update_image(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered image."""
    config1 = {"name": "Beer", "image_topic": "test_topic"}
    config2 = {"name": "Milk", "image_topic": "test_topic"}

    await help_test_discovery_update(
        hass, mqtt_mock_entry, image.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_image(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered image."""
    data1 = '{ "name": "Beer", "image_topic": "test_topic"}'
    with patch(
        "homeassistant.components.mqtt.image.MqttImage.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, image.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "image_topic": "test_topic"}'

    await help_test_discovery_broken(hass, mqtt_mock_entry, image.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT image device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT image device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG, ["test_topic"]
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, image.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        image.DOMAIN,
        DEFAULT_CONFIG,
        None,
        state_topic="test_topic",
        state_payload=b"ON",
    )


async def test_reloadable(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient
) -> None:
    """Test reloading the MQTT platform."""
    domain = image.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_setup_manual_entity_from_yaml(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup manual configured MQTT entity."""
    await mqtt_mock_entry()
    platform = image.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = image.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            image.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                },
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("topic", "payload1", "payload2"),
    [
        ("availability-topic", "online", "offline"),
        ("json-attributes-topic", '{"attr1": "val1"}', '{"attr1": "val2"}'),
    ],
)
async def test_skipped_async_ha_write_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    payload1: str,
    payload2: str,
) -> None:
    """Test a write state command is only called when there is change."""
    await mqtt_mock_entry()
    await help_test_skipped_async_ha_write_state(hass, topic, payload1, payload2)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                image.DOMAIN: {
                    "name": "test",
                    "url_topic": "test-topic",
                    "url_template": "{{ value_json.some_var * 1 }}",
                }
            }
        }
    ],
)
async def test_value_template_fails(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the rendering of MQTT value template fails."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, "test-topic", '{"some_var": null }')
    assert (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' rendering template"
        in caplog.text
    )
