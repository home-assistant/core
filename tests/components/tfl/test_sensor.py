"""Test the Transport for London sensor."""

from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError

from tflwrapper import stopPoint

from homeassistant.components.tfl.sensor import (
    ATTR_NEXT_ARRIVALS,
    ATTR_NEXT_THREE_ARRIVALS,
    StopPointSensor,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_DATA_SENSOR_ARRIVALS, MOCK_DATA_TFL_STATION_ARRIVALS


async def test_async_update_success(hass: HomeAssistant) -> None:
    """Tests a fully successful async_update."""

    stop_point_api: stopPoint = MagicMock()
    stop_point_api.getStationArrivals = MagicMock(
        return_value=MOCK_DATA_TFL_STATION_ARRIVALS
    )

    sensor = StopPointSensor(stop_point_api, "A stop point", "AAAAAAAA1", "12345")
    with patch.object(sensor, "hass", new=hass):
        await sensor.async_update()

    sensor_next_3 = sensor._attr_extra_state_attributes[ATTR_NEXT_THREE_ARRIVALS]
    sensor_all = sensor._attr_extra_state_attributes[ATTR_NEXT_ARRIVALS]

    assert sensor._attr_native_value == MOCK_DATA_SENSOR_ARRIVALS[0]["time_to_station"]
    assert sensor_next_3 == MOCK_DATA_SENSOR_ARRIVALS[:3]
    assert sensor_all == MOCK_DATA_SENSOR_ARRIVALS
    assert sensor.available is True


async def test_async_update_failed(hass: HomeAssistant) -> None:
    """Tests a failed async_update."""

    stop_point_api: stopPoint = MagicMock()
    stop_point_api.getStationArrivals = Mock(
        side_effect=HTTPError("http://test", 404, "Not Found", None, None)
    )

    sensor = StopPointSensor(stop_point_api, "A stop point", "AAAAAAAA1", "12345")
    with patch.object(sensor, "hass", new=hass):
        await sensor.async_update()

    assert sensor.available is False
