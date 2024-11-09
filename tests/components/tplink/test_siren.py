"""Tests for siren platform."""

from __future__ import annotations

from kasa import Device, Module
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import _mocked_device, setup_platform_for_device, snapshot_platform

from tests.common import MockConfigEntry

ENTITY_ID = "siren.hub"


@pytest.fixture
async def mocked_hub(hass: HomeAssistant) -> Device:
    """Return mocked tplink hub with an alarm module."""

    return _mocked_device(
        alias="hub",
        modules=[Module.Alarm],
        device_type=Device.Type.Hub,
    )


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

    alarm_module = mocked_hub.modules[Module.Alarm]

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    alarm_module.stop.assert_called()

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    alarm_module.play.assert_called()
