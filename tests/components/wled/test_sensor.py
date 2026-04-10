"""Tests for the WLED sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.wled.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.wled.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("init_integration")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2021-11-04 17:36:59+01:00")
async def test_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.wled_rgb_light_uptime",
        "sensor.wled_rgb_light_free_memory",
        "sensor.wled_rgb_light_wi_fi_signal",
        "sensor.wled_rgb_light_wi_fi_rssi",
        "sensor.wled_rgb_light_wi_fi_channel",
        "sensor.wled_rgb_light_wi_fi_bssid",
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default WLED sensors."""
    assert hass.states.get(entity_id) is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    "key",
    [
        "bssid",
        "channel",
        "rssi",
        "signal",
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_wifi_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    key: str,
) -> None:
    """Test missing Wi-Fi information from WLED device."""
    # Remove Wi-Fi info
    device = mock_wled.update.return_value
    device.info.wifi = None

    # Setup
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(f"sensor.wled_rgb_light_wi_fi_{key}"))
    assert state.state == STATE_UNKNOWN


async def test_no_current_measurement(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test missing current information when no max power is defined."""
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert hass.states.get("sensor.wled_rgb_light_estimated_current") is None


async def test_fail_when_other_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
) -> None:
    """Ensure no data are updated when mac address mismatch."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_ip"))
    assert state.state == "127.0.0.1"

    device = mock_wled.update.return_value
    device.info.mac_address = "invalid"

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_ip"))
    assert state.state == "unavailable"
