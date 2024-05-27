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
    ):
        mock_client.random_base32.return_value = "TOKEN_B"
        mock_totp = MagicMock()
        mock_totp.verify.return_value = True
        mock_totp.provisioning_uri.return_value = "test-uri"

        mock_client.TOTP.return_value = mock_totp

        yield mock_client


@pytest.fixture
def mock_qr() -> Generator[MagicMock, None, None]:
    """Mock a pyotp."""
    with (
        patch(
            "homeassistant.components.otp.config_flow._generate_qr_code",
            return_value="qr-code",
        ) as mock_client,
    ):
        yield mock_client.return_value
