"""Define tests for the Airzone coordinator."""

from unittest.mock import patch

from airzone_mqtt.exceptions import AirzoneMqttError

from homeassistant.components.airzone_mqtt.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .util import async_init_integration

from tests.common import async_fire_time_changed
from tests.typing import MqttMockHAClient


async def test_coordinator_client_connector_error(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test ClientConnectorError on coordinator update."""

    await async_init_integration(hass, mqtt_mock)

    with (
        patch(
            "homeassistant.components.airzone_mqtt.AirzoneMqttApi.update",
            side_effect=AirzoneMqttError,
        ) as mock_update,
    ):
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done()
        mock_update.assert_called_once()

        state = hass.states.get("sensor.room_1_temperature")
        assert state.state == STATE_UNAVAILABLE
