"""The tests for the uk_transport platform."""
import re
from unittest.mock import patch

import requests_mock

from homeassistant.components.uk_transport.sensor import (
    ATTR_ATCOCODE,
    ATTR_CALLING_AT,
    ATTR_LOCALITY,
    ATTR_NEXT_BUSES,
    ATTR_NEXT_TRAINS,
    ATTR_STATION_CODE,
    ATTR_STOP_NAME,
    CONF_API_APP_ID,
    CONF_API_APP_KEY,
    UkTransportSensor,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import now

from tests.common import load_fixture

BUS_ATCOCODE = "340000368SHE"
BUS_DIRECTION = "Wantage"
TRAIN_STATION_CODE = "WIM"
TRAIN_DESTINATION_NAME = "WAT"

VALID_CONFIG = {
    "sensor": {
        "platform": "uk_transport",
        CONF_API_APP_ID: "foo",
        CONF_API_APP_KEY: "ebcd1234",
        "queries": [
            {"mode": "bus", "origin": BUS_ATCOCODE, "destination": BUS_DIRECTION},
            {
                "mode": "train",
                "origin": TRAIN_STATION_CODE,
                "destination": TRAIN_DESTINATION_NAME,
            },
        ],
    }
}


async def test_bus(hass):
    """Test for operational uk_transport sensor with proper attributes."""
    with requests_mock.Mocker() as mock_req:
        uri = re.compile(UkTransportSensor.TRANSPORT_API_URL_BASE + "*")
        mock_req.get(uri, text=load_fixture("uk_transport_bus.json"))
        assert await async_setup_component(hass, "sensor", VALID_CONFIG)
        await hass.async_block_till_done()

    bus_state = hass.states.get("sensor.next_bus_to_wantage")
    assert None is not bus_state
    assert f"Next bus to {BUS_DIRECTION}" == bus_state.name
    assert BUS_ATCOCODE == bus_state.attributes[ATTR_ATCOCODE]
    assert "Harwell Campus" == bus_state.attributes[ATTR_LOCALITY]
    assert "Bus Station" == bus_state.attributes[ATTR_STOP_NAME]
    assert 2 == len(bus_state.attributes.get(ATTR_NEXT_BUSES))

    direction_re = re.compile(BUS_DIRECTION)
    for bus in bus_state.attributes.get(ATTR_NEXT_BUSES):
        assert None is not bus
        assert None is not direction_re.search(bus["direction"])


async def test_train(hass):
    """Test for operational uk_transport sensor with proper attributes."""
    with requests_mock.Mocker() as mock_req, patch(
        "homeassistant.util.dt.now", return_value=now().replace(hour=13)
    ):
        uri = re.compile(UkTransportSensor.TRANSPORT_API_URL_BASE + "*")
        mock_req.get(uri, text=load_fixture("uk_transport_train.json"))
        assert await async_setup_component(hass, "sensor", VALID_CONFIG)
        await hass.async_block_till_done()

    train_state = hass.states.get("sensor.next_train_to_WAT")
    assert None is not train_state
    assert f"Next train to {TRAIN_DESTINATION_NAME}" == train_state.name
    assert TRAIN_STATION_CODE == train_state.attributes[ATTR_STATION_CODE]
    assert TRAIN_DESTINATION_NAME == train_state.attributes[ATTR_CALLING_AT]
    assert 25 == len(train_state.attributes.get(ATTR_NEXT_TRAINS))

    assert (
        "London Waterloo"
        == train_state.attributes[ATTR_NEXT_TRAINS][0]["destination_name"]
    )
    assert "06:13" == train_state.attributes[ATTR_NEXT_TRAINS][0]["estimated"]
