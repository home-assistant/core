"""The tests for the Tasmota mixins."""
import copy
import json

from hatasmota.const import CONF_MAC
from hatasmota.utils import config_get_state_online, get_topic_tele_will

from homeassistant.components.tasmota.const import DEFAULT_PREFIX

from .test_common import DEFAULT_CONFIG

from tests.async_mock import call
from tests.common import async_fire_mqtt_message


async def test_availability_poll_state_once(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test several entities send a single message to update state."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["rl"][1] = 1
    config["swc"][0] = 1
    config["swc"][1] = 1
    poll_payload_relay = ""
    poll_payload_switch = "10"
    poll_topic_relay = "tasmota_49A3BC/cmnd/STATE"
    poll_topic_switch = "tasmota_49A3BC/cmnd/STATUS"

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Device online, verify poll for state
    async_fire_mqtt_message(
        hass,
        get_topic_tele_will(config),
        config_get_state_online(config),
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.assert_has_calls(
        [
            call(poll_topic_relay, poll_payload_relay, 0, False),
            call(poll_topic_switch, poll_payload_switch, 0, False),
        ],
        any_order=True,
    )
