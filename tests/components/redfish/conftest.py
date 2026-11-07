"""Fixtures for Redfish tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.redfish.const import CONF_BASE_URL, DOMAIN
from homeassistant.components.redfish.models import RedfishData, RedfishSystem
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Redfish config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="redfish-entry",
        title="Server",
        unique_id="https://bmc.example",
        data={
            CONF_BASE_URL: "https://bmc.example",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )


@pytest.fixture
def redfish_data() -> RedfishData:
    """Return representative parsed Redfish data."""
    return RedfishData(
        systems={
            "1": RedfishSystem(
                odata_id="/redfish/v1/Systems/1",
                system_id="1",
                name="Server",
                uuid="uuid-1",
                manufacturer="Acme",
                model="Model 1",
                serial_number="serial",
                power_state="On",
                reset_target="/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
                reset_types=frozenset(
                    {
                        "On",
                        "GracefulShutdown",
                        "ForceOff",
                        "GracefulRestart",
                        "ForceRestart",
                        "FullPowerCycle",
                    }
                ),
            ),
            "2": RedfishSystem(
                odata_id="/redfish/v1/Systems/2",
                system_id="2",
                name="Server without UUID",
                uuid=None,
                manufacturer=None,
                model=None,
                serial_number=None,
                power_state="Off",
                reset_target=None,
                reset_types=frozenset(),
            ),
        }
    )


@pytest.fixture
def mock_redfish_api(
    redfish_data: RedfishData,
) -> Generator[tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock]]:
    """Mock Redfish network operations."""
    with (
        patch(
            "homeassistant.components.redfish.api.RedfishApi.async_discover",
            new=AsyncMock(return_value=redfish_data),
        ) as discover,
        patch(
            "homeassistant.components.redfish.api.RedfishApi.async_reset",
            new=AsyncMock(),
        ) as reset,
        patch(
            "homeassistant.components.redfish.api.RedfishApi.async_login",
            new=AsyncMock(),
        ) as login,
        patch(
            "homeassistant.components.redfish.api.RedfishApi.async_logout",
            new=AsyncMock(),
        ) as logout,
    ):
        yield discover, reset, login, logout


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_redfish_api: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
) -> MockConfigEntry:
    """Set up the Redfish integration."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
