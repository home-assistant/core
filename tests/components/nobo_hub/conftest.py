"""Common fixtures for the Nobø Ecohub tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pynobo import nobo as pynobo_nobo
import pytest

from homeassistant.components.nobo_hub import PLATFORMS
from homeassistant.components.nobo_hub.const import (
    CONF_AUTO_DISCOVERED,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

SERIAL = "102000013098"
STORED_IP = "192.168.1.122"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nobo_hub.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_unload_entry() -> Generator[AsyncMock]:
    """Override async_unload_entry."""
    with patch(
        "homeassistant.components.nobo_hub.async_unload_entry", return_value=True
    ) as mock_unload_entry:
        yield mock_unload_entry


@pytest.fixture
def ip_address() -> str:
    """Return the stored IP address for the config entry."""
    return STORED_IP


@pytest.fixture
def auto_discovered() -> bool:
    """Return whether the config entry was auto-discovered."""
    return False


@pytest.fixture
def connect_exc() -> BaseException | None:
    """Exception to raise from hub.connect(), or None for success."""
    return None


@pytest.fixture
def mock_config_entry(ip_address: str, auto_discovered: bool) -> MockConfigEntry:
    """Return a mock Nobø Ecohub config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: ip_address,
            CONF_AUTO_DISCOVERED: auto_discovered,
        },
    )


@pytest.fixture
def mock_nobo_class(
    connect_exc: BaseException | None,
) -> Generator[MagicMock]:
    """Patch the integration's imported `nobo` class with a populated hub instance."""
    with patch("homeassistant.components.nobo_hub.nobo", autospec=True) as mock_cls:
        hub = mock_cls.return_value
        if connect_exc is not None:
            hub.connect.side_effect = connect_exc

        hub.hub_serial = SERIAL
        hub.hub_info = {
            "name": "My Eco Hub",
            "serial": SERIAL,
            "software_version": "115",
            "hardware_version": "hw",
        }
        hub.zones = {
            "1": {
                "zone_id": "1",
                "name": "Living room",
                "week_profile_id": "0",
                "temp_comfort_c": "21",
                "temp_eco_c": "17",
            },
        }
        model = MagicMock()
        # Direct assignment overrides MagicMock's auto-attr for `.name`.
        model.name = "Panel heater"
        model.has_temp_sensor = True
        hub.components = {
            "200000059091": {
                "serial": "200000059091",
                "name": "Floor sensor",
                "zone_id": "1",
                "model": model,
            },
        }
        hub.week_profiles = {
            "0": {"week_profile_id": "0", "name": "Default", "profile": "00000"},
        }
        hub.overrides = {
            "988": {
                "mode": pynobo_nobo.API.OVERRIDE_MODE_NORMAL,
                "target_type": pynobo_nobo.API.OVERRIDE_TARGET_GLOBAL,
                "target_id": "-1",
            },
        }
        hub.temperatures = {"200000059091": "21.5"}

        hub.get_current_zone_mode.return_value = pynobo_nobo.API.NAME_COMFORT
        hub.get_zone_override_mode.return_value = pynobo_nobo.API.NAME_NORMAL
        hub.get_current_zone_temperature.return_value = "20.5"
        hub.get_current_component_temperature.return_value = "21.5"

        mock_cls.async_discover_hubs.return_value = set()
        yield mock_cls


@pytest.fixture
def mock_nobo_hub(mock_nobo_class: MagicMock) -> MagicMock:
    """Return the pre-configured pynobo hub instance."""
    return mock_nobo_class.return_value


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up (default: the integration's full list)."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Nobø Ecohub integration."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.nobo_hub.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry
