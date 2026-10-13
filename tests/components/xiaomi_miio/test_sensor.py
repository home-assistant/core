"""The tests for the xiaomi_miio sensor component."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.xiaomi_miio import UPDATE_INTERVAL
from homeassistant.components.xiaomi_miio.const import CONF_FLOW_TYPE, DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed

MODEL_JSQS = "deerma.humidifier.jsqs"


async def setup_component(hass: HomeAssistant, entity_name: str) -> None:
    """Set up component helper."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="654321",
        title=entity_name,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "0.0.0.0",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: MODEL_JSQS,
            CONF_MAC: TEST_MAC,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_test(hass: HomeAssistant):
    """Initialize test xiaomi_miio for sensor entity."""

    mock_humidifier = MagicMock()
    mock_status = MagicMock()

    mock_status.temperature = 22.5
    mock_status.relative_humidity = 45
    mock_humidifier.status.return_value = mock_status

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[Platform.SENSOR],
        ),
        patch(
            "homeassistant.components.xiaomi_miio.AirHumidifierJsqs",
            return_value=mock_humidifier,
        ),
    ):
        yield mock_status


async def test_humidifier_jsqs_sensors(hass: HomeAssistant, setup_test) -> None:
    """Test the initial states and coordinator updates of JSQS sensors."""

    entity_name = "test_humidifier"
    await setup_component(hass, entity_name)

    sensor_ids = hass.states.async_entity_ids(SENSOR_DOMAIN)

    temp_entity_id = next(
        entity_id for entity_id in sensor_ids if "temperature" in entity_id
    )
    humidity_entity_id = next(
        entity_id for entity_id in sensor_ids if "humidity" in entity_id
    )

    state_temp = hass.states.get(temp_entity_id)
    assert state_temp is not None
    assert state_temp.state == "22.5"

    state_humidity = hass.states.get(humidity_entity_id)
    assert state_humidity is not None
    assert state_humidity.state == "45"

    setup_test.temperature = 24.1
    setup_test.relative_humidity = 52

    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state_temp_updated = hass.states.get(temp_entity_id)
    assert state_temp_updated.state == "24.1"

    state_humidity_updated = hass.states.get(humidity_entity_id)
    assert state_humidity_updated.state == "52"
