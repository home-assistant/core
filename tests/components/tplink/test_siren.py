"""Tests for siren platform."""

from __future__ import annotations

from kasa import Device, Feature, Module
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, Platform
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

ENTITY_ID = "siren.hub"


@pytest.fixture
async def mocked_hub(hass: HomeAssistant) -> Device:
    """Return mocked tplink hub with an alarm module and features."""

    features = [
        _mocked_feature(
            "alarm",
            value=False,
            category=Feature.Category.Info,
            type_=Feature.Type.BinarySensor,
        ),
        _mocked_feature(
            "test_alarm",
        ),
        _mocked_feature(
            "stop_alarm",
        ),
    ]

    return _mocked_device(
        alias="hub",
        modules=[Module.Alarm],
        features=features,
        device_type=Device.Type.Hub,
    )


async def test_siren(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mocked_hub: Device,
) -> None:
    """Test initialization."""
    await setup_platform_for_device(hass, mock_config_entry, Platform.SIREN, mocked_hub)

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_siren"

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mocked_hub: Device,
) -> None:
    """Snapshot test."""
    await setup_platform_for_device(hass, mock_config_entry, Platform.SIREN, mocked_hub)

    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )


async def test_turn_on_and_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_hub: Device
) -> None:
    """Test that turn_on and turn_off services work as expected."""
    await setup_platform_for_device(hass, mock_config_entry, Platform.SIREN, mocked_hub)

    play_alarm = mocked_hub.features["test_alarm"]
    stop_alarm = mocked_hub.features["stop_alarm"]

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    stop_alarm.set_value.assert_called_with(True)

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    play_alarm.set_value.assert_called_with(True)
