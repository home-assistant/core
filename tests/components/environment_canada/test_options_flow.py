"""Test the Environment Canada options flow."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.environment_canada.const import (
    CONF_RADAR_LAYER,
    CONF_RADAR_LEGEND,
    CONF_RADAR_OPACITY,
    CONF_RADAR_RADIUS,
    CONF_RADAR_TIMESTAMP,
    DEFAULT_RADAR_LAYER,
    DEFAULT_RADAR_LEGEND,
    DEFAULT_RADAR_OPACITY,
    DEFAULT_RADAR_RADIUS,
    DEFAULT_RADAR_TIMESTAMP,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import FIXTURE_USER_INPUT, build_mocks, init_integration

from tests.common import MockConfigEntry


async def _setup_with_options(
    hass: HomeAssistant, ec_data: dict[str, Any], options: dict[str, Any]
) -> MagicMock:
    """Set up the integration and return the patched ECMap constructor mock."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, title="Home", options=options
    )
    config_entry.add_to_hass(hass)

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
        await hass.config_entries.async_setup(config_entry.entry_id)
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
    # Saving options reloads the entry so the new radar settings take effect.
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
    options: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test the radar ECMap is constructed from the saved options."""
    ecmap = await _setup_with_options(hass, ec_data, options)

    ecmap.assert_called_once()
    kwargs = ecmap.call_args.kwargs
    assert kwargs["layer"] == expected["layer"]
    assert kwargs["legend"] is expected["legend"]
    assert kwargs["timestamp"] is expected["timestamp"]
    assert kwargs["layer_opacity"] == expected["layer_opacity"]
    assert isinstance(kwargs["layer_opacity"], int)
    assert kwargs["radius"] == expected["radius"]
    assert isinstance(kwargs["radius"], int)
