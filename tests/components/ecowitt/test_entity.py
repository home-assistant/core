"""Test the Ecowitt entity availability handling."""

from datetime import timedelta

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.ecowitt.const import DOMAIN
from homeassistant.components.ecowitt.entity import UNAVAILABLE_TIMEOUT
from homeassistant.const import CONF_WEBHOOK_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

WEBHOOK_ID = "ecowitt_test_webhook"

BASE_PAYLOAD = {
    "PASSKEY": "ABCDEF0123456789",
    "stationtype": "GW1200C_V1.3.4",
    "model": "GW1200C",
    "freq": "433M",
    "dateutc": "2025-03-13 09:03:39",
    "tempinf": "75.56",
    "humidityin": "42",
}

INDOOR_TEMP = "sensor.gw1200c_indoor_temperature"
CH1_TEMP = "sensor.gw1200c_soil_temperature_1"


@pytest.fixture
async def client(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> TestClient:
    """Set up the Ecowitt integration and return a webhook client."""
    await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_WEBHOOK_ID: WEBHOOK_ID})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return await hass_client_no_auth()


async def _post(hass: HomeAssistant, client: TestClient, data: dict[str, str]) -> None:
    """Post a payload to the webhook."""
    resp = await client.post(f"/api/webhook/{WEBHOOK_ID}", data=data)
    assert resp.status == 200
    await hass.async_block_till_done()


async def test_sensor_unavailable_when_no_longer_reported(
    hass: HomeAssistant, client: TestClient, freezer: FrozenDateTimeFactory
) -> None:
    """Test a sensor missing from uploads becomes unavailable."""
    await _post(hass, client, BASE_PAYLOAD | {"tf_ch1": "66.56"})
    assert hass.states.get(INDOOR_TEMP).state != STATE_UNAVAILABLE
    assert hass.states.get(CH1_TEMP).state == "19.2"

    # The gateway stops including the channel 1 sensor in its uploads
    for _ in range(10):
        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass)
        await _post(hass, client, BASE_PAYLOAD)

    # 10 minutes without data for channel 1, below the timeout
    assert hass.states.get(CH1_TEMP).state == "19.2"

    freezer.tick(timedelta(seconds=UNAVAILABLE_TIMEOUT - 600 + 1))
    async_fire_time_changed(hass)
    await _post(hass, client, BASE_PAYLOAD)

    assert hass.states.get(CH1_TEMP).state == STATE_UNAVAILABLE
    assert hass.states.get(INDOOR_TEMP).state != STATE_UNAVAILABLE

    # The sensor comes back
    await _post(hass, client, BASE_PAYLOAD | {"tf_ch1": "68.0"})
    assert hass.states.get(CH1_TEMP).state == "20.0"


async def test_all_sensors_unavailable_when_gateway_stops(
    hass: HomeAssistant, client: TestClient, freezer: FrozenDateTimeFactory
) -> None:
    """Test all sensors become unavailable when the gateway stops uploading."""
    await _post(hass, client, BASE_PAYLOAD | {"tf_ch1": "66.56"})

    freezer.tick(timedelta(seconds=UNAVAILABLE_TIMEOUT - 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(INDOOR_TEMP).state != STATE_UNAVAILABLE
    assert hass.states.get(CH1_TEMP).state != STATE_UNAVAILABLE

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(INDOOR_TEMP).state == STATE_UNAVAILABLE
    assert hass.states.get(CH1_TEMP).state == STATE_UNAVAILABLE
