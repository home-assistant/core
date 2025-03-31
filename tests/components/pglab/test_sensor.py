"""The tests for the PG LAB Electronics sensor."""

import json

from freezegun import freeze_time
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .test_common import get_device_discovery_payload, send_discovery_message

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


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
    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=0,
    )

    await send_discovery_message(hass, payload)

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
