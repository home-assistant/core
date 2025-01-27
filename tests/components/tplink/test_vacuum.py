"""Tests for vacuum platform."""

from __future__ import annotations

from kasa import Device, Feature, Module
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    VacuumActivity,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    DEVICE_ID,
    _mocked_device,
    _mocked_feature,
    setup_platform_for_device,
    snapshot_platform,
)

from tests.common import MockConfigEntry

ENTITY_ID = "vacuum.my_vacuum"


@pytest.fixture
async def mocked_vacuum(hass: HomeAssistant) -> Device:
    """Return mocked tplink vacuum."""

    # Need to manually create the fan speed preset feature,
    # as we are going to read its choices through it
    feats = [
        _mocked_feature(
            "vacuum_fan_speed",
            type_=Feature.Type.Choice,
            category=Feature.Category.Config,
            choices=["Quiet", "Max"],
            value="Max",
            expected_module_key="fan_speed_preset",
        ),
    ]

    return _mocked_device(
        modules=[Module.Clean, Module.Speaker], features=feats, alias="my_vacuum"
    )


async def test_vacuum(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mocked_vacuum: Device,
) -> None:
    """Test initialization."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.VACUUM, mocked_vacuum
    )

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries

    entity_registry = er.async_get(hass)

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}-vacuum"

    state = hass.states.get(ENTITY_ID)
    assert state.state == VacuumActivity.DOCKED

    assert state.attributes[ATTR_FAN_SPEED] == "Max"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 100


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mocked_vacuum: Device,
) -> None:
    """Test vacuum states."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.VACUUM, mocked_vacuum
    )
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("service_call", "method", "params"),
    [
        (SERVICE_START, "start", {}),
        (SERVICE_PAUSE, "pause", {}),
        (SERVICE_RETURN_TO_BASE, "return_home", {}),
        (SERVICE_SET_FAN_SPEED, "set_fan_speed_preset", {ATTR_FAN_SPEED: "Quiet"}),
    ],
)
async def test_vacuum_module(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_vacuum: Device,
    service_call: str,
    method: str,
    params: dict,
) -> None:
    """Test that all vacuum commands work correctly."""
    vacuum = mocked_vacuum
    clean = vacuum.modules[Module.Clean]

    await setup_platform_for_device(hass, mock_config_entry, Platform.VACUUM, vacuum)

    mock_method = getattr(clean, method)

    service_data = {ATTR_ENTITY_ID: ENTITY_ID}
    service_data |= params

    await hass.services.async_call(
        VACUUM_DOMAIN, service_call, service_data, blocking=True
    )

    # Is this required when using blocking=True?
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_method.assert_called()
