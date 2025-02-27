"""The tests for the PG LAB Electronics sensor."""

import json

from freezegun import freeze_time
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def send_discovery_message(hass: HomeAssistant) -> None:
    """Send mqtt discovery message."""

    topic = "pglab/discovery/E-Board-DD53AC85/config"
    payload = {
        "ip": "192.168.1.16",
        "mac": "80:34:28:1B:18:5A",
        "name": "test",
        "hw": "1.0.7",
        "fw": "1.0.0",
        "type": "E-Board",
        "id": "E-Board-DD53AC85",
        "manufacturer": "PG LAB Electronics",
        "params": {"shutters": 0, "boards": "00000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()


@freeze_time("2024-02-26 01:21:34")
@pytest.mark.parametrize(
    "sensor_suffix",
    [
        "temperature",
        "mpu_voltage",
        "run_time",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mqtt_mock: MqttMockHAClient,
    setup_pglab,
    sensor_suffix: str,
) -> None:
    """Check if sensors are properly created and updated."""

    # send the discovery message to make E-BOARD device discoverable
    await send_discovery_message(hass)

    # check initial sensors state
    state = hass.states.get(f"sensor.test_{sensor_suffix}")
    assert state == snapshot(name=f"initial_sensor_{sensor_suffix}")

    # update sensors value via mqtt
    update_payload = {"temp": 33.4, "volt": 3.31, "rtime": 1000}
    async_fire_mqtt_message(hass, "pglab/test/sensor/value", json.dumps(update_payload))
    await hass.async_block_till_done()

    # check updated sensors state
    state = hass.states.get(f"sensor.test_{sensor_suffix}")
    assert state == snapshot(name=f"updated_sensor_{sensor_suffix}")
