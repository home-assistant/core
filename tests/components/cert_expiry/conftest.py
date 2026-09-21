"""Configuration for cert_expiry tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.cert_expiry.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import HOST, PORT
from .helpers import certificate_expiring, future_timestamp


@pytest.fixture
def cert_verified() -> Generator[None]:
    """Report every certificate as passing chain and hostname verification."""
    with patch(
        "homeassistant.components.cert_expiry.coordinator.HandshakePolicyVerifier.verify_cert",
        return_value=None,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cert_expiry.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=f"{HOST}:{PORT}",
    )


@pytest.fixture
def mock_async_get_cert(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Return a handshake for a certificate that expires 100 days after the frozen time.

    Depends on hass so the test's default time zone is established (by the hass
    fixture) before future_timestamp() resolves its naive datetime, regardless of
    the order in which the test requests these two fixtures.
    """
    with patch(
        "homeassistant.components.cert_expiry.coordinator.async_get_cert",
        return_value=certificate_expiring(future_timestamp(100)),
    ) as mock_get_cert:
        yield mock_get_cert
