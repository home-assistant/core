"""Test the Environment Canada (EC) config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import xml.etree.ElementTree as ET

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.environment_canada.const import (
    CONF_RADAR_LAYER,
    CONF_RADAR_LEGEND,
    CONF_RADAR_OPACITY,
    CONF_RADAR_RADIUS,
    CONF_RADAR_TIMESTAMP,
    CONF_STATION,
    DEFAULT_RADAR_LAYER,
    DEFAULT_RADAR_LEGEND,
    DEFAULT_RADAR_OPACITY,
    DEFAULT_RADAR_RADIUS,
    DEFAULT_RADAR_TIMESTAMP,
    DOMAIN,
)
from homeassistant.const import CONF_LANGUAGE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import build_mocks, init_integration

from tests.common import MockConfigEntry

FAKE_CONFIG = {
    CONF_STATION: "123",
    CONF_LANGUAGE: "English",
    CONF_LATITUDE: 42.42,
    CONF_LONGITUDE: -42.42,
}
FAKE_TITLE = "Universal title!"
FAKE_STATIONS = [
    {"label": "Toronto, ON", "value": "123"},
    {"label": "Ottawa, ON", "value": "456"},
    {"label": "Montreal, QC", "value": "789"},
]


def mocked_ec():
    """Mock the env_canada library."""
    ec_mock = MagicMock()
    ec_mock.station_id = FAKE_CONFIG[CONF_STATION]
    ec_mock.lat = FAKE_CONFIG[CONF_LATITUDE]
    ec_mock.lon = FAKE_CONFIG[CONF_LONGITUDE]
    ec_mock.language = FAKE_CONFIG[CONF_LANGUAGE]
    ec_mock.metadata.location = FAKE_TITLE

    ec_mock.update = AsyncMock()

    return patch(
        "homeassistant.components.environment_canada.config_flow.ECWeather",
        return_value=ec_mock,
    )


def mocked_stations():
    """Mock the station list."""
    return patch(
        "homeassistant.components.environment_canada.config_flow.get_ec_sites_list",
        return_value=FAKE_STATIONS,
    )


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test creating an entry."""
    with (
        mocked_ec(),
        mocked_stations(),
        patch(
            "homeassistant.components.environment_canada.async_setup_entry",
            return_value=True,
        ),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], FAKE_CONFIG
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == FAKE_CONFIG
        assert result["title"] == FAKE_TITLE


async def test_create_same_entry_twice(hass: HomeAssistant) -> None:
    """Test duplicate entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=FAKE_CONFIG,
        unique_id="123-english",
    )
    entry.add_to_hass(hass)

    with (
        mocked_ec(),
        mocked_stations(),
        patch(
            "homeassistant.components.environment_canada.async_setup_entry",
            return_value=True,
        ),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], FAKE_CONFIG
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "error",
    [
        (aiohttp.ClientResponseError(Mock(), (), status=404), "bad_station_id"),
        (aiohttp.ClientResponseError(Mock(), (), status=400), "error_response"),
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (ET.ParseError, "bad_station_id"),
        (ValueError, "unknown"),
    ],
)
async def test_exception_handling(hass: HomeAssistant, error) -> None:
    """Test exception handling."""
    exc, base_error = error
    with (
        mocked_stations(),
        patch(
            "homeassistant.components.environment_canada.config_flow.ECWeather",
            side_effect=exc,
        ),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {},
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": base_error}


async def test_lat_lon_not_specified(hass: HomeAssistant) -> None:
    """Test that the import step works when coordinates are not specified."""
    with (
        mocked_ec(),
        mocked_stations(),
        patch(
            "homeassistant.components.environment_canada.async_setup_entry",
            return_value=True,
        ),
    ):
        fake_config = dict(FAKE_CONFIG)
        del fake_config[CONF_LATITUDE]
        del fake_config[CONF_LONGITUDE]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=fake_config
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == FAKE_CONFIG
        assert result["title"] == FAKE_TITLE


async def test_coordinates_without_station(hass: HomeAssistant) -> None:
    """Test setup with coordinates but no station ID."""
    with (
        mocked_ec(),
        mocked_stations(),
        patch(
            "homeassistant.components.environment_canada.async_setup_entry",
            return_value=True,
        ),
    ):
        # Config with coordinates but no station
        config_no_station = {
            CONF_LANGUAGE: "English",
            CONF_LATITUDE: 42.42,
            CONF_LONGITUDE: -42.42,
        }
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], config_no_station
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == FAKE_CONFIG
        assert result["title"] == FAKE_TITLE


async def _setup_with_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    ec_data: dict[str, Any],
    options: dict[str, Any],
) -> MagicMock:
    """Set up the integration and return the patched ECMap constructor mock."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)

    weather_mock, aqhi_mock, radar_mock = build_mocks(ec_data)
    ecmap = MagicMock(return_value=radar_mock)

    with (
        patch(
            "homeassistant.components.environment_canada.ECWeather",
            return_value=weather_mock,
        ),
        patch(
            "homeassistant.components.environment_canada.ECAirQuality",
            return_value=aqhi_mock,
        ),
        patch("homeassistant.components.environment_canada.ECMap", ecmap),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return ecmap


async def test_options_flow_form(hass: HomeAssistant, ec_data: dict[str, Any]) -> None:
    """Test the options form shows all radar fields."""
    config_entry = await init_integration(hass, ec_data)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys = {str(k) for k in result["data_schema"].schema}
    assert schema_keys == {
        CONF_RADAR_LAYER,
        CONF_RADAR_LEGEND,
        CONF_RADAR_TIMESTAMP,
        CONF_RADAR_OPACITY,
        CONF_RADAR_RADIUS,
    }


async def test_options_flow_save(hass: HomeAssistant, ec_data: dict[str, Any]) -> None:
    """Test submitting the options form stores the values and reloads the entry."""
    config_entry = await init_integration(hass, ec_data)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    new_options = {
        CONF_RADAR_LAYER: "rain",
        CONF_RADAR_LEGEND: True,
        CONF_RADAR_TIMESTAMP: False,
        CONF_RADAR_OPACITY: 30,
        CONF_RADAR_RADIUS: 100,
    }
    with patch(
        "homeassistant.components.environment_canada.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], new_options
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == new_options
    assert mock_setup_entry.called


async def test_options_flow_prefills_saved_options(
    hass: HomeAssistant, ec_data: dict[str, Any]
) -> None:
    """Test the options form is pre-filled with previously saved values."""
    saved_options = {
        CONF_RADAR_LAYER: "snow",
        CONF_RADAR_LEGEND: True,
        CONF_RADAR_TIMESTAMP: False,
        CONF_RADAR_OPACITY: 50,
        CONF_RADAR_RADIUS: 300,
    }
    config_entry = await init_integration(hass, ec_data, options=saved_options)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults[CONF_RADAR_LAYER] == "snow"
    assert defaults[CONF_RADAR_LEGEND] is True
    assert defaults[CONF_RADAR_TIMESTAMP] is False
    assert defaults[CONF_RADAR_OPACITY] == 50
    assert defaults[CONF_RADAR_RADIUS] == 300


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param(
            {},
            {
                "layer": DEFAULT_RADAR_LAYER,
                "legend": DEFAULT_RADAR_LEGEND,
                "timestamp": DEFAULT_RADAR_TIMESTAMP,
                "layer_opacity": DEFAULT_RADAR_OPACITY,
                "radius": DEFAULT_RADAR_RADIUS,
            },
            id="defaults",
        ),
        pytest.param(
            {
                CONF_RADAR_LAYER: "snow",
                CONF_RADAR_LEGEND: True,
                CONF_RADAR_TIMESTAMP: False,
                CONF_RADAR_OPACITY: 40.0,
                CONF_RADAR_RADIUS: 150.0,
            },
            {
                "layer": "snow",
                "legend": True,
                "timestamp": False,
                "layer_opacity": 40,
                "radius": 150,
            },
            id="custom",
        ),
    ],
)
async def test_ecmap_built_from_options(
    hass: HomeAssistant,
    ec_data: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    options: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test the radar ECMap is constructed from the saved options."""
    ecmap = await _setup_with_options(hass, mock_config_entry, ec_data, options)

    ecmap.assert_called_once()
    kwargs = ecmap.call_args.kwargs
    assert kwargs["layer"] == expected["layer"]
    assert kwargs["legend"] is expected["legend"]
    assert kwargs["timestamp"] is expected["timestamp"]
    assert kwargs["layer_opacity"] == expected["layer_opacity"]
    assert isinstance(kwargs["layer_opacity"], int)
    assert kwargs["radius"] == expected["radius"]
    assert isinstance(kwargs["radius"], int)
