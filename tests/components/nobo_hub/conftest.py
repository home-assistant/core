"""Common fixtures for the Nobø Ecohub tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pynobo import nobo as pynobo_nobo
import pytest

from homeassistant.components.nobo_hub.const import (
    CONF_AUTO_DISCOVERED,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS
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


def make_hub_mock(*, connect_exc: BaseException | None = None) -> MagicMock:
    """Build a mock pynobo.nobo instance with one zone, component, and profile."""
    hub = MagicMock()
    hub.connect = AsyncMock(side_effect=connect_exc)
    hub.start = AsyncMock()
    hub.stop = AsyncMock()
    hub.close = AsyncMock()
    hub.async_create_override = AsyncMock()
    hub.async_update_zone = AsyncMock()

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

    # State lookups
    hub.get_current_zone_mode = MagicMock(return_value=pynobo_nobo.API.NAME_COMFORT)
    hub.get_zone_override_mode = MagicMock(return_value=pynobo_nobo.API.NAME_NORMAL)
    hub.get_current_zone_temperature = MagicMock(return_value="20.5")
    hub.get_current_component_temperature = MagicMock(return_value="21.5")
    return hub


def make_entry(
    hass: HomeAssistant,
    *,
    auto_discovered: bool = False,
    ip_address: str = STORED_IP,
) -> MockConfigEntry:
    """Build a mock config entry for Nobø Ecohub and add it to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: ip_address,
            CONF_AUTO_DISCOVERED: auto_discovered,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def integration_setup(
    hass: HomeAssistant,
) -> AsyncGenerator[tuple[MockConfigEntry, MagicMock]]:
    """Set up the integration with a fully-mocked hub and sample data."""
    entry = make_entry(hass, auto_discovered=False)
    hub = make_hub_mock()
    with patch("homeassistant.components.nobo_hub.nobo") as mock_cls:
        mock_cls.return_value = hub
        mock_cls.async_discover_hubs = AsyncMock(return_value=set())
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, hub
