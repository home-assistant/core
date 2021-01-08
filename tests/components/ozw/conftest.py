"""Helpers for tests."""
import json

import pytest

from .common import MQTTMessage

from tests.async_mock import patch
from tests.common import load_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa


@pytest.fixture(name="generic_data", scope="session")
def generic_data_fixture():
    """Load generic MQTT data and return it."""
    return load_fixture("ozw/generic_network_dump.csv")


@pytest.fixture(name="fan_data", scope="session")
def fan_data_fixture():
    """Load fan MQTT data and return it."""
    return load_fixture("ozw/fan_network_dump.csv")


@pytest.fixture(name="light_data", scope="session")
def light_data_fixture():
    """Load light dimmer MQTT data and return it."""
    return load_fixture("ozw/light_network_dump.csv")


@pytest.fixture(name="light_new_ozw_data", scope="session")
def light_new_ozw_data_fixture():
    """Load light dimmer MQTT data and return it."""
    return load_fixture("ozw/light_new_ozw_network_dump.csv")


@pytest.fixture(name="light_no_ww_data", scope="session")
def light_no_ww_data_fixture():
    """Load light dimmer MQTT data and return it."""
    return load_fixture("ozw/light_no_ww_network_dump.csv")


@pytest.fixture(name="light_no_cw_data", scope="session")
def light_no_cw_data_fixture():
    """Load light dimmer MQTT data and return it."""
    return load_fixture("ozw/light_no_cw_network_dump.csv")


@pytest.fixture(name="light_wc_data", scope="session")
def light_wc_only_data_fixture():
    """Load light dimmer MQTT data and return it."""
    return load_fixture("ozw/light_wc_network_dump.csv")


@pytest.fixture(name="cover_data", scope="session")
def cover_data_fixture():
    """Load cover MQTT data and return it."""
    return load_fixture("ozw/cover_network_dump.csv")


@pytest.fixture(name="cover_gdo_data", scope="session")
def cover_gdo_data_fixture():
    """Load cover_gdo MQTT data and return it."""
    return load_fixture("ozw/cover_gdo_network_dump.csv")


@pytest.fixture(name="climate_data", scope="session")
def climate_data_fixture():
    """Load climate MQTT data and return it."""
    return load_fixture("ozw/climate_network_dump.csv")


@pytest.fixture(name="lock_data", scope="session")
def lock_data_fixture():
    """Load lock MQTT data and return it."""
    return load_fixture("ozw/lock_network_dump.csv")


@pytest.fixture(name="string_sensor_data", scope="session")
def string_sensor_fixture():
    """Load string sensor MQTT data and return it."""
    return load_fixture("ozw/sensor_string_value_network_dump.csv")


@pytest.fixture(name="sent_messages")
def sent_messages_fixture():
    """Fixture to capture sent messages."""
    sent_messages = []

    with patch(
        "homeassistant.components.mqtt.async_publish",
        side_effect=lambda hass, topic, payload: sent_messages.append(
            {"topic": topic, "payload": json.loads(payload)}
        ),
    ):
        yield sent_messages


@pytest.fixture(name="fan_msg")
async def fan_msg_fixture(hass):
    """Return a mock MQTT msg with a fan actuator message."""
    fan_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/fan.json")
    )
    message = MQTTMessage(topic=fan_json["topic"], payload=fan_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="light_msg")
async def light_msg_fixture(hass):
    """Return a mock MQTT msg with a light actuator message."""
    light_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/light.json")
    )
    message = MQTTMessage(topic=light_json["topic"], payload=light_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="light_no_rgb_msg")
async def light_no_rgb_msg_fixture(hass):
    """Return a mock MQTT msg with a light actuator message."""
    light_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/light_no_rgb.json")
    )
    message = MQTTMessage(topic=light_json["topic"], payload=light_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="light_rgb_msg")
async def light_rgb_msg_fixture(hass):
    """Return a mock MQTT msg with a light actuator message."""
    light_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/light_rgb.json")
    )
    message = MQTTMessage(topic=light_json["topic"], payload=light_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="light_pure_rgb_msg")
async def light_pure_rgb_msg_fixture(hass):
    """Return a mock MQTT msg with a pure rgb light actuator message."""
    light_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/light_pure_rgb.json")
    )
    message = MQTTMessage(topic=light_json["topic"], payload=light_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="switch_msg")
async def switch_msg_fixture(hass):
    """Return a mock MQTT msg with a switch actuator message."""
    switch_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/switch.json")
    )
    message = MQTTMessage(topic=switch_json["topic"], payload=switch_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="sensor_msg")
async def sensor_msg_fixture(hass):
    """Return a mock MQTT msg with a sensor change message."""
    sensor_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/sensor.json")
    )
    message = MQTTMessage(topic=sensor_json["topic"], payload=sensor_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="binary_sensor_msg")
async def binary_sensor_msg_fixture(hass):
    """Return a mock MQTT msg with a binary_sensor change message."""
    sensor_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/binary_sensor.json")
    )
    message = MQTTMessage(topic=sensor_json["topic"], payload=sensor_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="binary_sensor_alt_msg")
async def binary_sensor_alt_msg_fixture(hass):
    """Return a mock MQTT msg with a binary_sensor change message."""
    sensor_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/binary_sensor_alt.json")
    )
    message = MQTTMessage(topic=sensor_json["topic"], payload=sensor_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="cover_msg")
async def cover_msg_fixture(hass):
    """Return a mock MQTT msg with a cover level change message."""
    sensor_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/cover.json")
    )
    message = MQTTMessage(topic=sensor_json["topic"], payload=sensor_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="cover_gdo_msg")
async def cover_gdo_msg_fixture(hass):
    """Return a mock MQTT msg with a cover barrier state change message."""
    sensor_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/cover_gdo.json")
    )
    message = MQTTMessage(topic=sensor_json["topic"], payload=sensor_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="climate_msg")
async def climate_msg_fixture(hass):
    """Return a mock MQTT msg with a climate mode change message."""
    sensor_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/climate.json")
    )
    message = MQTTMessage(topic=sensor_json["topic"], payload=sensor_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="lock_msg")
async def lock_msg_fixture(hass):
    """Return a mock MQTT msg with a lock actuator message."""
    lock_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "ozw/lock.json")
    )
    message = MQTTMessage(topic=lock_json["topic"], payload=lock_json["payload"])
    message.encode()
    return message


@pytest.fixture(name="stop_addon")
def mock_install_addon():
    """Mock stop add-on."""
    with patch("homeassistant.components.hassio.async_stop_addon") as stop_addon:
        yield stop_addon


@pytest.fixture(name="uninstall_addon")
def mock_uninstall_addon():
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.hassio.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon


@pytest.fixture(name="get_addon_discovery_info")
def mock_get_addon_discovery_info():
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.async_get_addon_discovery_info"
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info
