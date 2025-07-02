"""Test Autoskope diagnostics."""

from unittest.mock import patch

from autoskope_client.models import Vehicle

from homeassistant.components.autoskope.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vehicles_list,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = mock_vehicles_list

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check diagnostics structure
        assert "entry" in diagnostics
        assert "coordinator" in diagnostics
        assert "vehicles" in diagnostics
        assert "vehicles_count" in diagnostics

        # Check entry info
        assert diagnostics["entry"]["title"] == mock_config_entry.title

        # Check coordinator info
        assert "last_update_success" in diagnostics["coordinator"]
        assert "update_interval" in diagnostics["coordinator"]

        # Check vehicles info
        assert diagnostics["vehicles_count"] == len(mock_vehicles_list)
        vehicle = mock_vehicles_list[0]
        assert vehicle.id in diagnostics["vehicles"]
        vehicle_diag = diagnostics["vehicles"][vehicle.id]
        assert vehicle_diag["name"] == vehicle.name
        assert vehicle_diag["model"] == vehicle.model
        assert "battery_voltage" in vehicle_diag
        assert "has_position" in vehicle_diag

        # Check sensitive data is redacted
        assert diagnostics["entry"]["data"]["username"] == "**REDACTED**"
        assert diagnostics["entry"]["data"]["password"] == "**REDACTED**"


async def test_config_entry_diagnostics_no_vehicles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics with no vehicles."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = []

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check no vehicles
        assert diagnostics["vehicles_count"] == 0
        assert diagnostics["vehicles"] == {}


async def test_config_entry_diagnostics_vehicle_without_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics with vehicle without position."""
    vehicle_no_position = Vehicle(
        id="12345",
        name="Test Vehicle",
        position=None,
        external_voltage=12.5,
        battery_voltage=3.7,
        gps_quality=1.2,
        imei="123456789012345",
        model="Autoskope",
    )

    mock_config_entry.add_to_hass(hass)

    with (
        patch("autoskope_client.api.AutoskopeApi.authenticate", return_value=True),
        patch("autoskope_client.api.AutoskopeApi.get_vehicles") as mock_get_vehicles,
    ):
        mock_get_vehicles.return_value = [vehicle_no_position]

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check vehicle without position
        vehicle_diag = diagnostics["vehicles"][vehicle_no_position.id]
        assert vehicle_diag["has_position"] is False
        assert vehicle_diag["position"]["speed"] is None
        assert vehicle_diag["position"]["park_mode"] is None
        assert vehicle_diag["position"]["has_coordinates"] is False
