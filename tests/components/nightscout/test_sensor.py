"""The sensor tests for the Nightscout platform."""

from unittest.mock import patch

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
from py_nightscout.models import ServerStatus
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nightscout.const import (
    ATTR_DELTA,
    ATTR_DEVICE,
    ATTR_DIRECTION,
)
from homeassistant.components.nightscout.coordinator import (
    SCAN_INTERVAL,
    STATUS_SCAN_INTERVAL,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import ATTR_DATE, ATTR_ICON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    GLUCOSE_READINGS,
    SERVER_STATUS_STATUS_ONLY,
    init_integration,
    init_integration_empty_response,
)

URGENT_HIGH_THRESHOLD_ENTITY_ID = "sensor.nightscout_urgent_high_threshold"


async def test_sensor_state(hass: HomeAssistant) -> None:
    """Test sensor state data."""
    await init_integration(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor.state == str(
        GLUCOSE_READINGS[0].sgv  # pylint: disable=maybe-no-member
    )


async def test_sensor_error(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the sensor becomes unavailable on update errors and recovers."""
    await init_integration(hass)

    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
        side_effect=ClientConnectionError(),
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.blood_sugar").state == STATE_UNAVAILABLE

    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
        return_value=GLUCOSE_READINGS,
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.blood_sugar").state == str(
        GLUCOSE_READINGS[0].sgv  # pylint: disable=maybe-no-member
    )


async def test_sensor_empty_response(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the sensor becomes unavailable if no readings are returned."""
    await init_integration(hass)

    with patch(
        "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
        return_value=[],
    ):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.blood_sugar").state == STATE_UNAVAILABLE


async def test_sensor_attributes(hass: HomeAssistant) -> None:
    """Test sensor attributes."""
    await init_integration(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    reading = GLUCOSE_READINGS[0]
    assert reading is not None

    attr = test_glucose_sensor.attributes
    assert attr[ATTR_DATE] == reading.date  # pylint: disable=maybe-no-member
    assert attr[ATTR_DELTA] == reading.delta  # pylint: disable=maybe-no-member
    assert attr[ATTR_DEVICE] == reading.device  # pylint: disable=maybe-no-member
    assert attr[ATTR_DIRECTION] == reading.direction  # pylint: disable=maybe-no-member
    assert attr[ATTR_ICON] == "mdi:arrow-bottom-right"
    assert attr[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_threshold_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the threshold sensors."""
    entry = await init_integration(hass, SERVER_STATUS_STATUS_ONLY)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_no_threshold_sensors_without_thresholds(hass: HomeAssistant) -> None:
    """Test no threshold sensors are created if the server reports none."""
    await init_integration(hass)

    assert hass.states.get(URGENT_HIGH_THRESHOLD_ENTITY_ID) is None


async def test_threshold_sensors_without_readings(hass: HomeAssistant) -> None:
    """Test the threshold sensors load when there are no glucose readings."""
    await init_integration_empty_response(hass, SERVER_STATUS_STATUS_ONLY)

    assert hass.states.get("sensor.blood_sugar").state == STATE_UNAVAILABLE
    assert hass.states.get(URGENT_HIGH_THRESHOLD_ENTITY_ID).state == "260"


async def test_threshold_sensors_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the threshold sensors follow the server status."""
    await init_integration(hass, SERVER_STATUS_STATUS_ONLY)
    assert hass.states.get(URGENT_HIGH_THRESHOLD_ENTITY_ID).state == "260"

    updated_status = ServerStatus.new_from_json_dict(
        {
            "name": "nightscout",
            "settings": {
                "thresholds": {
                    "bgHigh": 250,
                    "bgTargetTop": 170,
                    "bgTargetBottom": 75,
                    "bgLow": 60,
                }
            },
        }
    )
    with (
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_sgvs",
            return_value=GLUCOSE_READINGS,
        ),
        patch(
            "homeassistant.components.nightscout.NightscoutAPI.get_server_status",
            side_effect=[ClientConnectionError(), updated_status],
        ),
    ):
        freezer.tick(STATUS_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (
            hass.states.get(URGENT_HIGH_THRESHOLD_ENTITY_ID).state == STATE_UNAVAILABLE
        )

        freezer.tick(STATUS_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(URGENT_HIGH_THRESHOLD_ENTITY_ID).state == "250"
