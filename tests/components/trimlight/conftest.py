"""Fixtures for the Trimlight integration tests."""

from collections.abc import Generator
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, MagicMock, patch

from aiotrimlight import TrimlightDeviceInfo, TrimlightICType, TrimlightLightState
import pytest

from homeassistant.components.trimlight.const import CONF_DID, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

HOST = "192.0.2.10"
DID = "544c0003a1b2c3d4e5f6"
MAC = "a1:b2:c3:d4:e5:f6"
NAME = "Test controller"
ENTITY_ID = "light.test_controller"


@pytest.fixture
def ic_type() -> TrimlightICType:
    """Return the controller's default color capability."""
    return TrimlightICType.RGB


@pytest.fixture
def initial_is_on() -> bool:
    """Return the controller's initial power state."""
    return True


@pytest.fixture
def mock_trimlight(
    ic_type: TrimlightICType, initial_is_on: bool
) -> Generator[MagicMock]:
    """Mock the API client without simulating device behavior."""
    with (
        patch(
            "homeassistant.components.trimlight.TrimlightClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.trimlight.config_flow.TrimlightClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_device_info.return_value = TrimlightDeviceInfo(
            firmware_version="1.0.38.1.0.13r", ic_type=ic_type
        )
        client.get_light_state.return_value = TrimlightLightState(
            is_on=initial_is_on,
            brightness=128,
            red=10,
            green=20,
            blue=30,
            warm_white=40,
            cold_white=50,
        )
        client.set_light_state.return_value = None
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a registered config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_HOST: HOST, CONF_DID: DID, CONF_MAC: MAC},
        unique_id=DID,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def zeroconf_info() -> ZeroconfServiceInfo:
    """Return discovery information for the controller."""
    ip_address = IPv4Address(HOST)
    return ZeroconfServiceInfo(
        ip_address=ip_address,
        ip_addresses=[ip_address],
        port=8586,
        hostname="Test-controller.local.",
        type="_tlight._tcp.local.",
        name="Test-controller._tlight._tcp.local.",
        properties={"did": DID, "name": NAME},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flow tests from loading the integration."""
    with patch(
        "homeassistant.components.trimlight.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Load the integration through HA's config entry interface."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
