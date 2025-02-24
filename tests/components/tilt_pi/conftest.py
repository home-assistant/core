"""Common fixtures for the Tilt Pi tests."""

import pytest


@pytest.fixture
def tiltpi_api_all_response() -> list[dict[str, any]]:
    """Fixture for TiltPi API response."""
    return [
        {
            "mac": "00:1A:2B:3C:4D:5E",
            "Color": "red",
            "Temp": "68.5",
            "SG": "1.052",
        }
    ]
