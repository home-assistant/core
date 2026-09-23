"""Tests for the Arcam FMJ config entry setup."""

from arcam.fmj.state import State
import pytest

from homeassistant.components.arcam_fmj.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_UUID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("player_setup")
async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the zone 2 device links to the zone 1 device via via_device_id."""
    zone1_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UUID), mock_config_entry.entry_id
    )
    assert zone1_device is not None

    zone2_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_UUID}-2"), mock_config_entry.entry_id
    )
    assert zone2_device is not None
    assert zone2_device.via_device_id == zone1_device.id


@pytest.mark.usefixtures("player_setup")
async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    state_1: State,
) -> None:
    """Test the discovered model and software version are registered."""
    state_1.model = "SDP-58"
    state_1.revision = "2.0.0"

    await mock_config_entry.runtime_data.coordinators[1].async_refresh()
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_UUID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == "SDP-58"
    assert device.sw_version == "2.0.0"
