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
    """Test missing current information when the device estimates no current."""
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert hass.states.get("sensor.wled_rgb_light_estimated_current") is None


async def test_current_measurement_once_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the current sensors are added once the device reports a current."""
    # WLED reports no current while the light is off.
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert hass.states.get("sensor.wled_rgb_light_estimated_current") is None

    device.info.leds.max_power = 850
    device.info.leds.power = 470
    # pylint: disable-next=home-assistant-tests-coordinator-async-refresh
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_max_current"))
    assert state.state == "850"
    assert (state := hass.states.get("sensor.wled_rgb_light_estimated_current"))
    assert state.state == "470"

    # Later updates don't add them again.
    # pylint: disable-next=home-assistant-tests-coordinator-async-refresh
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert "does not generate unique IDs" not in caplog.text


async def test_current_measurement_kept_when_not_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test current sensors added before stay while the device reports none."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.wled_rgb_light_estimated_current")

    # The light is off when Home Assistant starts again.
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 0
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.wled_rgb_light_max_current"))
    assert state.state == "0"
    assert (state := hass.states.get("sensor.wled_rgb_light_estimated_current"))
    assert state.state == "0"


async def test_current_measurement_with_per_output_limiters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test estimated current is available when limiting current per output."""
    # Per output limiters leave the global power budget unset, while the
    # device keeps estimating and reporting the current it draws.
    device = mock_wled.update.return_value
    device.info.leds.max_power = 0
    device.info.leds.power = 3193

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wled_rgb_light_max_current") is None
    assert (state := hass.states.get("sensor.wled_rgb_light_estimated_current"))
    assert state.state == "3193"


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
