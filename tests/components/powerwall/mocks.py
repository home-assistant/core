"""Mocks for powerwall."""

from unittest.mock import MagicMock, patch

MOCK_UNIQUE_ID = "192.168.1.100"

# Mock meter data matching pypowerwall poll("/api/meters/aggregates") response
MOCK_METERS_DATA = {
    "site": {
        "last_communication_time": "2024-01-01T12:00:00+00:00",
        "instant_power": 500,
        "instant_reactive_power": -100,
        "instant_apparent_power": 510,
        "frequency": 50.0,
        "energy_exported": 1000000,
        "energy_imported": 500000,
        "instant_average_voltage": 230.5,
        "instant_total_current": 2.17,
    },
    "battery": {
        "last_communication_time": "2024-01-01T12:00:00+00:00",
        "instant_power": -1500,
        "instant_reactive_power": 0,
        "instant_apparent_power": 1500,
        "frequency": 50.0,
        "energy_exported": 800000,
        "energy_imported": 900000,
        "instant_average_voltage": 230.0,
        "instant_total_current": 6.52,
    },
    "load": {
        "last_communication_time": "2024-01-01T12:00:00+00:00",
        "instant_power": 750,
        "instant_reactive_power": -50,
        "instant_apparent_power": 752,
        "frequency": 0,
        "energy_exported": 0,
        "energy_imported": 2000000,
        "instant_average_voltage": 230.5,
        "instant_total_current": 3.25,
    },
    "solar": {
        "last_communication_time": "2024-01-01T12:00:00+00:00",
        "instant_power": 2750,
        "instant_reactive_power": 0,
        "instant_apparent_power": 2750,
        "frequency": 50.0,
        "energy_exported": 3000000,
        "energy_imported": 0,
        "instant_average_voltage": 230.0,
        "instant_total_current": 11.96,
    },
}

MOCK_METERS_DATA_NO_SOLAR = {
    "site": MOCK_METERS_DATA["site"],
    "battery": MOCK_METERS_DATA["battery"],
    "load": MOCK_METERS_DATA["load"],
}

MOCK_GRID_STATUS_DATA = {
    "grid_status": "SystemGridConnected",
    "grid_services_active": False,
}

MOCK_SOE_DATA = {
    "percentage": 85.5,
}


def create_mock_powerwall(
    level: float = 85.5,
    grid_status: str = "UP",
    site_name: str | None = None,
    version: str | None = None,
    meters: dict | None = None,
    grid_data: dict | None = None,
) -> MagicMock:
    """Create a mock pypowerwall.Powerwall instance."""
    mock_pw = MagicMock()

    # Convenience methods
    mock_pw.level.return_value = level
    mock_pw.grid_status.return_value = grid_status
    mock_pw.site_name.return_value = site_name
    mock_pw.version.return_value = version
    mock_pw.din.return_value = None
    mock_pw.power.return_value = {
        "site": 500,
        "solar": 2750,
        "battery": -1500,
        "load": 750,
    }
    mock_pw.solar.return_value = 2750
    mock_pw.battery.return_value = -1500
    mock_pw.grid.return_value = 500
    mock_pw.load.return_value = 750

    # Poll method for raw API access
    if meters is None:
        meters = MOCK_METERS_DATA
    if grid_data is None:
        grid_data = MOCK_GRID_STATUS_DATA

    def mock_poll(endpoint: str) -> dict | None:
        if endpoint == "/api/meters/aggregates":
            return meters
        if endpoint == "/api/system_status/grid_status":
            return grid_data
        if endpoint == "/api/system_status/soe":
            return {"percentage": level}
        return None

    mock_pw.poll.side_effect = mock_poll

    return mock_pw


def create_mock_powerwall_pw3() -> MagicMock:
    """Create a mock for Powerwall 3 (limited API)."""
    return create_mock_powerwall(
        site_name=None,
        version=None,
    )


def create_mock_powerwall_pw2() -> MagicMock:
    """Create a mock for Powerwall 2 (full API)."""
    mock_pw = create_mock_powerwall(
        site_name="My Home",
        version="23.44.0",
    )
    mock_pw.din.return_value = "1232100-12-B--T12345678901"
    return mock_pw


def patch_powerwall(mock_pw: MagicMock | None = None):
    """Patch pypowerwall.Powerwall constructor."""
    if mock_pw is None:
        mock_pw = create_mock_powerwall_pw3()

    return patch(
        "homeassistant.components.powerwall.pypowerwall.Powerwall",
        return_value=mock_pw,
    )
