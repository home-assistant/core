"""Define common test fixtures for Enphase Envoy."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import jwt
from pyenphase import EnvoyTokenAuth
import pytest

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config, serial_number):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title=f"Envoy {serial_number}" if serial_number else "Envoy",
        unique_id=serial_number,
        data=config,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> dict[str, str]:
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.fixture(name="mock_authenticate")
def mock_authenticate() -> AsyncMock:
    """Define a mocked Envoy.authenticate fixture."""
    return AsyncMock()


@pytest.fixture(name="mock_auth")
def mock_auth(serial_number):
    """Define a mocked EnvoyAuth fixture."""
    token = jwt.encode(
        payload={"name": "envoy", "exp": 1907837780}, key="secret", algorithm="HS256"
    )
    return EnvoyTokenAuth("127.0.0.1", token=token, envoy_serial=serial_number)


@pytest.fixture(name="mock_setup")
def mock_setup() -> AsyncMock:
    """Define a mocked Envoy.setup fixture."""
    return AsyncMock()


@pytest.fixture(name="serial_number")
def serial_number_fixture() -> str:
    """Define a serial number fixture."""
    return "1234"


@pytest.fixture(name="mock_go_on_grid")
def go_on_grid_fixture() -> AsyncMock:
    """Define a go_on_grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_go_off_grid")
def go_off_grid_fixture() -> AsyncMock:
    """Define a go_off_grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_update_dry_contact")
def update_dry_contact_fixture() -> AsyncMock:
    """Define a update_dry_contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_open_dry_contact")
def open_dry_contact_fixture() -> AsyncMock:
    """Define a gopen dry contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_close_dry_contact")
def close_dry_contact_fixture() -> AsyncMock:
    """Define a close dry contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_enable_charge_from_grid")
def enable_charge_from_grid_fixture() -> AsyncMock:
    """Define a enable charge from grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_disable_charge_from_grid")
def disable_charge_from_grid_fixture() -> AsyncMock:
    """Define a disable charge from grid fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_set_storage_mode")
def set_storage_mode_fixture() -> AsyncMock:
    """Define a update_dry_contact fixture."""
    return AsyncMock(return_value="[]")


@pytest.fixture(name="mock_set_reserve_soc")
def set_reserve_soc_fixture() -> AsyncMock:
    """Define a update_dry_contact fixture."""
    return AsyncMock(return_value="[]")
