"""Provide common fixtures."""
from __future__ import annotations

from collections.abc import Generator
import time
from unittest.mock import MagicMock, patch

from pybalboa.balboa import text_heatmode
import pytest


@pytest.fixture(name="client")
def client_fixture() -> Generator[None, MagicMock, None]:
    """Mock balboa."""
    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi", autospec=True
    ) as mock_balboa:
        # common attributes
        client = mock_balboa.return_value
        client.connected = True
        client.lastupd = time.time()
        client.new_data_cb = None
        client.connect.return_value = True
        client.get_macaddr.return_value = "ef:ef:ef:c0:ff:ee"
        client.get_model_name.return_value = "FakeSpa"
        client.get_ssid.return_value = "V0.0"

        # constants should preferably be moved in the library
        # to be class attributes or further refactored
        client.TSCALE_C = 1
        client.TSCALE_F = 0
        client.HEATMODE_READY = 0
        client.HEATMODE_REST = 1
        client.HEATMODE_RNR = 2
        client.TIMESCALE_12H = 0
        client.TIMESCALE_24H = 1
        client.PUMP_OFF = 0
        client.PUMP_LOW = 1
        client.PUMP_HIGH = 2
        client.TEMPRANGE_LOW = 0
        client.TEMPRANGE_HIGH = 1
        client.tmin = [
            [50.0, 10.0],
            [80.0, 26.0],
        ]
        client.tmax = [
            [80.0, 26.0],
            [104.0, 40.0],
        ]
        client.BLOWER_OFF = 0
        client.BLOWER_LOW = 1
        client.BLOWER_MEDIUM = 2
        client.BLOWER_HIGH = 3
        client.FILTER_OFF = 0
        client.FILTER_1 = 1
        client.FILTER_2 = 2
        client.FILTER_1_2 = 3
        client.OFF = 0
        client.ON = 1
        client.HEATSTATE_IDLE = 0
        client.HEATSTATE_HEATING = 1
        client.HEATSTATE_HEAT_WAITING = 2
        client.VOLTAGE_240 = 240
        client.VOLTAGE_UNKNOWN = 0
        client.HEATERTYPE_STANDARD = "Standard"
        client.HEATERTYPE_UNKNOWN = "Unknown"

        # Climate attributes
        client.heatmode = 0
        client.get_heatmode_stringlist.return_value = text_heatmode
        client.get_tempscale.return_value = client.TSCALE_F
        client.have_blower.return_value = False

        # Climate methods
        client.get_heatstate.return_value = 0
        client.get_blower.return_value = 0
        client.get_curtemp.return_value = 20.0
        client.get_settemp.return_value = 20.0

        def get_heatmode(text=False):
            """Ask for the current heatmode."""
            if text:
                return text_heatmode[client.heatmode]
            return client.heatmode

        client.get_heatmode.side_effect = get_heatmode
        yield client


@pytest.fixture(autouse=True)
def set_temperature_wait():
    """Mock set temperature wait time."""
    with patch("homeassistant.components.balboa.climate.SET_TEMPERATURE_WAIT", new=0):
        yield
