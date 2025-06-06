"""Tests for the diagnostics data provided by the everHome integration."""

from unittest.mock import AsyncMock

from ecotracker.data import EcoTrackerData

from homeassistant.components.everhome.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test diagnostics for config entry."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.serial_number == "abcdef123456"
    assert device_entry.sw_version == "1.0.0"

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert (
        result["data"]
        == EcoTrackerData.from_json(load_fixture("data.json", DOMAIN)).to_dict()
    )
