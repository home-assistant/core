"""Tests for Yardian sensors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pyyardian import OperationInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.components.yardian.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("sensor_platform_only")


def _make_oper_info(**overrides: object) -> OperationInfo:
    base = {
        "iRainDelay": 3600,
        "iSensorDelay": 5,
        "iWaterHammerDuration": 2,
        "iStandby": 1,
        "fFreezePrevent": 1,
    }
    base.update(overrides)
    return OperationInfo(**base)


async def _async_trigger_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: object,
) -> None:
    """Snapshot all Yardian sensor entities."""

    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_diagnostic_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: object,
) -> None:
    """Diagnostic sensors are disabled by default."""

    await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.yardian_smart_sprinkler_zone_delay",
        "sensor.yardian_smart_sprinkler_water_hammer_reduction",
    ):
        reg_entry = entity_registry.async_get(entity_id)
        assert reg_entry is not None
        assert reg_entry.disabled
        assert reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zone_delay_sensor_interprets_timestamp_and_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Zone delay interprets timestamps and guards against invalid values."""

    freezer.move_to(datetime(2024, 1, 1, tzinfo=UTC))
    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "yid123_zone_delay"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "5"

    absolute_delay = int(
        (dt_util.utcnow() + SCAN_INTERVAL + timedelta(minutes=2)).timestamp()
    )
    mock_yardian_client.fetch_oper_info.return_value = _make_oper_info(
        iSensorDelay=absolute_delay
    )
    await _async_trigger_refresh(hass, freezer)
    assert hass.states.get(entity_id).state == "120"

    mock_yardian_client.fetch_oper_info.return_value = _make_oper_info(
        iSensorDelay="invalid"
    )
    await _async_trigger_refresh(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    mock_yardian_client.fetch_oper_info.return_value = _make_oper_info(
        iSensorDelay=None
    )
    await _async_trigger_refresh(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
