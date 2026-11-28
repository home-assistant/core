"""Tests for NEPViewer sensor platform."""

from datetime import timedelta
import logging
from unittest.mock import MagicMock

from aionepviewer import (
    Device,
    DeviceStatisticsOverview,
    NepAuthError,
    NepConnectionError,
    SiteModulesData,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nepviewer.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import LAST_REPORTED, api_timestamp

pytestmark = pytest.mark.freeze_time(LAST_REPORTED)

SITE_ENTITY_ID = "sensor.test_site_current_power"
DEVICE_ENTITY_ID = "sensor.test_device_current_power"
LAST_REPORTED_ENTITY_ID = "sensor.test_device_last_reported"
PANEL_ENTITY_ID = "sensor.panel_1_current_power"


@pytest.mark.usefixtures("mock_nepviewer")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entity registration and states."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that sensors become unavailable when the API cannot be reached."""
    caplog.set_level(logging.INFO)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"

    mock_nepviewer.get_site_overview.side_effect = NepConnectionError
    for _ in range(2):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(SITE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("nepviewer is unavailable") == 1

    mock_nepviewer.get_site_overview.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"
    assert caplog.text.count("Fetching nepviewer data recovered") == 1


async def test_missing_panel(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that only the panel becomes unavailable when it is no longer reported."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(PANEL_ENTITY_ID).state == "750.0"

    mock_nepviewer.get_site_modules.return_value = SiteModulesData({"list": []})
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(PANEL_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"


async def test_reauth_started(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that rejected credentials start a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nepviewer.get_site_overview.side_effect = NepAuthError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SITE_ENTITY_ID).state == STATE_UNAVAILABLE
    (flow,) = hass.config_entries.flow.async_progress()
    assert flow["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize(
    ("power", "timeout"),
    [
        pytest.param(1500.0, timedelta(minutes=90), id="producing"),
        pytest.param(0.0, timedelta(days=1), id="idle"),
    ],
)
async def test_not_reporting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
    power: float,
    timeout: timedelta,
) -> None:
    """Test that sensors are unavailable while the inverter does not report."""
    overview = mock_nepviewer.get_device_statistics_overview.return_value
    overview.raw_data["totalNow"] = power
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to(LAST_REPORTED + timeout - timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"
    assert hass.states.get(DEVICE_ENTITY_ID).state == str(power)
    assert hass.states.get(PANEL_ENTITY_ID).state == "750.0"

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SITE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(DEVICE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(PANEL_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(LAST_REPORTED_ENTITY_ID).state == LAST_REPORTED.isoformat()

    overview.raw_data["lastUpdateTime"] = api_timestamp(dt_util.utcnow())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"
    assert hass.states.get(DEVICE_ENTITY_ID).state == str(power)
    assert hass.states.get(PANEL_ENTITY_ID).state == "750.0"


async def test_one_device_not_reporting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the site stays available while another inverter reports."""
    freezer.move_to(LAST_REPORTED + timedelta(hours=2))
    stale = mock_nepviewer.get_device_statistics_overview.return_value
    fresh = DeviceStatisticsOverview(
        {**stale.raw_data, "lastUpdateTime": api_timestamp(dt_util.utcnow())}
    )
    mock_nepviewer.get_devices.return_value.append(
        Device({"sid": "test_sid", "sn": "FRESH_SN", "alias": "Fresh Device"})
    )
    mock_nepviewer.get_device_statistics_overview.side_effect = {
        "TEST_SN": stale,
        "FRESH_SN": fresh,
    }.get
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(DEVICE_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.fresh_device_current_power").state == "1500.0"
    assert hass.states.get(SITE_ENTITY_ID).state == "1500.0"


@pytest.mark.parametrize(
    ("overview", "site_detail"),
    [
        pytest.param({"lastUpdateTime": 0}, {}, id="no_timestamp"),
        pytest.param({}, {"timezone": ""}, id="no_time_zone"),
    ],
)
async def test_unknown_last_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer: MagicMock,
    overview: dict[str, int],
    site_detail: dict[str, str],
) -> None:
    """Test that values are kept when the report time is unknown."""
    mock_nepviewer.get_device_statistics_overview.return_value.raw_data.update(overview)
    mock_nepviewer.get_site_detail.return_value.raw_data.update(site_detail)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(LAST_REPORTED_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(DEVICE_ENTITY_ID).state == "1500.0"
