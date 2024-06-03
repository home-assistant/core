"""Common fixtures for the One-Time Password (OTP) tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.otp.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pyotp() -> Generator[MagicMock, None, None]:
    """Mock a pyotp."""
    with (
        patch(
            "homeassistant.components.otp.config_flow.pyotp",
        ) as mock_client,
        patch("homeassistant.components.otp.sensor.pyotp", new=mock_client),
    ):
        mock_totp = MagicMock()
        mock_totp.now.return_value = 123456
        mock_client.TOTP.return_value = mock_totp
        yield mock_client


@pytest.fixture(name="otp_config_entry")
def mock_otp_config_entry() -> MockConfigEntry:
    """Mock otp configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "OTP Sensor",
            CONF_TOKEN: "2FX5FBSYRE6VEC2FSHBQCRKO2GNDVZ52",
        },
        unique_id="2FX5FBSYRE6VEC2FSHBQCRKO2GNDVZ52",
    )
