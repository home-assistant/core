"""The tests for the rmvtransport platform."""
import datetime

from homeassistant.setup import async_setup_component

from tests.async_mock import patch

VALID_CONFIG_MINIMAL = {
    "sensor": {"platform": "rmvtransport", "next_departure": [{"station": "3000010"}]}
}

VALID_CONFIG_NAME = {
    "sensor": {
        "platform": "rmvtransport",
        "next_departure": [{"station": "3000010", "name": "My Station"}],
    }
}

VALID_CONFIG_MISC = {
    "sensor": {
        "platform": "rmvtransport",
        "next_departure": [
            {
                "station": "3000010",
                "lines": [21, "S8"],
                "max_journeys": 2,
                "time_offset": 10,
            }
        ],
    }
}

VALID_CONFIG_DEST = {
    "sensor": {
        "platform": "rmvtransport",
        "next_departure": [
            {
                "station": "3000010",
                "destinations": [
                    "Frankfurt (Main) Flughafen Regionalbahnhof",
                    "Frankfurt (Main) Stadion",
                ],
            }
        ],
    }
}


def get_departures_mock():
    """Mock rmvtransport departures loading."""
    data = {
        "station": "Frankfurt (Main) Hauptbahnhof",
        "stationId": "3000010",
        "filter": "11111111111",
        "journeys": [
            {
                "product": "Tram",
                "number": 12,
                "trainId": "1123456",
                "direction": "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                "departure_time": datetime.datetime(2018, 8, 6, 14, 21),
                "minutes": 7,
                "delay": 3,
                "stops": [
                    "Frankfurt (Main) Willy-Brandt-Platz",
                    "Frankfurt (Main) Römer/Paulskirche",
                    "Frankfurt (Main) Börneplatz",
                    "Frankfurt (Main) Konstablerwache",
                    "Frankfurt (Main) Bornheim Mitte",
                    "Frankfurt (Main) Saalburg-/Wittelsbacherallee",
                    "Frankfurt (Main) Eissporthalle/Festplatz",
                    "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                ],
                "info": None,
                "info_long": None,
                "icon": "https://products/32_pic.png",
            },
            {
                "product": "Bus",
                "number": 21,
                "trainId": "1234567",
                "direction": "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                "departure_time": datetime.datetime(2018, 8, 6, 14, 22),
                "minutes": 8,
                "delay": 1,
                "stops": [
                    "Frankfurt (Main) Weser-/Münchener Straße",
                    "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                ],
                "info": None,
                "info_long": None,
                "icon": "https://products/32_pic.png",
            },
            {
                "product": "Bus",
                "number": 12,
                "trainId": "1234568",
                "direction": "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                "departure_time": datetime.datetime(2018, 8, 6, 14, 25),
                "minutes": 11,
                "delay": 1,
                "stops": ["Frankfurt (Main) Stadion"],
                "info": None,
                "info_long": None,
                "icon": "https://products/32_pic.png",
            },
            {
                "product": "Bus",
                "number": 21,
                "trainId": "1234569",
                "direction": "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                "departure_time": datetime.datetime(2018, 8, 6, 14, 25),
                "minutes": 11,
                "delay": 1,
                "stops": [],
                "info": None,
                "info_long": None,
                "icon": "https://products/32_pic.png",
            },
            {
                "product": "Bus",
                "number": 12,
                "trainId": "1234570",
                "direction": "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                "departure_time": datetime.datetime(2018, 8, 6, 14, 25),
                "minutes": 11,
                "delay": 1,
                "stops": [],
                "info": None,
                "info_long": None,
                "icon": "https://products/32_pic.png",
            },
            {
                "product": "Bus",
                "number": 21,
                "trainId": "1234571",
                "direction": "Frankfurt (Main) Hugo-Junkers-Straße/Schleife",
                "departure_time": datetime.datetime(2018, 8, 6, 14, 25),
                "minutes": 11,
                "delay": 1,
                "stops": [],
                "info": None,
                "info_long": None,
                "icon": "https://products/32_pic.png",
            },
        ],
    }
    return data


def get_no_departures_mock():
    """Mock no departures in results."""
    data = {
        "station": "Frankfurt (Main) Hauptbahnhof",
        "stationId": "3000010",
        "filter": "11111111111",
        "journeys": [],
    }
    return data


async def test_rmvtransport_min_config(hass):
    """Test minimal rmvtransport configuration."""
    with patch(
        "RMVtransport.RMVtransport.get_departures", return_value=get_departures_mock(),
    ):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL) is True
        await hass.async_block_till_done()

    state = hass.states.get("sensor.frankfurt_main_hauptbahnhof")
    assert state.state == "7"
    assert state.attributes["departure_time"] == datetime.datetime(2018, 8, 6, 14, 21)
    assert (
        state.attributes["direction"] == "Frankfurt (Main) Hugo-Junkers-Straße/Schleife"
    )
    assert state.attributes["product"] == "Tram"
    assert state.attributes["line"] == 12
    assert state.attributes["icon"] == "mdi:tram"
    assert state.attributes["friendly_name"] == "Frankfurt (Main) Hauptbahnhof"


async def test_rmvtransport_name_config(hass):
    """Test custom name configuration."""
    with patch(
        "RMVtransport.RMVtransport.get_departures", return_value=get_departures_mock(),
    ):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG_NAME)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.my_station")
    assert state.attributes["friendly_name"] == "My Station"


async def test_rmvtransport_misc_config(hass):
    """Test misc configuration."""
    with patch(
        "RMVtransport.RMVtransport.get_departures", return_value=get_departures_mock(),
    ):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG_MISC)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.frankfurt_main_hauptbahnhof")
    assert state.attributes["friendly_name"] == "Frankfurt (Main) Hauptbahnhof"
    assert state.attributes["line"] == 21


async def test_rmvtransport_dest_config(hass):
    """Test destination configuration."""
    with patch(
        "RMVtransport.RMVtransport.get_departures", return_value=get_departures_mock(),
    ):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG_DEST)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.frankfurt_main_hauptbahnhof")
    assert state.state == "11"
    assert (
        state.attributes["direction"] == "Frankfurt (Main) Hugo-Junkers-Straße/Schleife"
    )
    assert state.attributes["line"] == 12
    assert state.attributes["minutes"] == 11
    assert state.attributes["departure_time"] == datetime.datetime(2018, 8, 6, 14, 25)


async def test_rmvtransport_no_departures(hass):
    """Test for no departures."""
    with patch(
        "RMVtransport.RMVtransport.get_departures",
        return_value=get_no_departures_mock(),
    ):
        assert await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.frankfurt_main_hauptbahnhof")
    assert not state
