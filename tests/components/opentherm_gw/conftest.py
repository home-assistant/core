"""Test configuration for opentherm_gw."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyotgw.vars import OTGW, OTGW_ABOUT
import pytest

from homeassistant.components.opentherm_gw import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_NAME

from tests.common import MockConfigEntry

VERSION_TEST = "4.2.5"
MINIMAL_STATUS = {OTGW: {OTGW_ABOUT: f"OpenTherm Gateway {VERSION_TEST}"}}
MOCK_GATEWAY_ID = "mock_gateway"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opentherm_gw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pyotgw() -> Generator[MagicMock]:
    """Mock a pyotgw.OpenThermGateway object."""
    with (
        patch(
            "homeassistant.components.opentherm_gw.OpenThermGateway",
            return_value=MagicMock(
                connect=AsyncMock(return_value=MINIMAL_STATUS),
                set_control_setpoint=AsyncMock(),
                set_max_relative_mod=AsyncMock(),
                disconnect=AsyncMock(),
            ),
        ) as mock_gateway,
        patch(
            "homeassistant.components.opentherm_gw.config_flow.pyotgw.OpenThermGateway",
            new=mock_gateway,
        ),
    ):
        yield mock_gateway


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock an OpenTherm Gateway config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Mock Gateway",
        data={
            CONF_NAME: "Mock Gateway",
            CONF_DEVICE: "/dev/null",
            CONF_ID: MOCK_GATEWAY_ID,
        },
        options={},
    )
