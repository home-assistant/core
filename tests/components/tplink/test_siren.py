"""Tests for siren platform."""

from __future__ import annotations

from kasa import Device, Module
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN as SIREN_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
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


@pytest.mark.parametrize(
    ("max_volume", "volume_level", "expected_volume"),
    [
        pytest.param(3, 0.1, 1, id="smart-10%"),
        pytest.param(3, 0.3, 1, id="smart-30%"),
        pytest.param(3, 0.99, 3, id="smart-99%"),
        pytest.param(3, 1, 3, id="smart-100%"),
        pytest.param(10, 0.1, 1, id="smartcam-10%"),
        pytest.param(10, 0.3, 3, id="smartcam-30%"),
        pytest.param(10, 0.99, 10, id="smartcam-99%"),
        pytest.param(10, 1, 10, id="smartcam-100%"),
    ],
)
async def test_turn_on_with_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_hub: Device,
    max_volume: int,
    volume_level: float,
    expected_volume: int,
) -> None:
    """Test that turn_on volume parameters work as expected."""

    alarm_module = mocked_hub.modules[Module.Alarm]
    alarm_volume_feat = alarm_module.get_feature("alarm_volume")
    assert alarm_volume_feat
    alarm_volume_feat.maximum_value = max_volume

    await setup_platform_for_device(hass, mock_config_entry, Platform.SIREN, mocked_hub)

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [ENTITY_ID], ATTR_VOLUME_LEVEL: volume_level},
        blocking=True,
    )

    alarm_module.play.assert_called_with(
        volume=expected_volume, duration=None, sound=None
    )


async def test_turn_on_with_duration_and_sound(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_hub: Device,
) -> None:
    """Test that turn_on tone and duration parameters work as expected."""

    alarm_module = mocked_hub.modules[Module.Alarm]

    await setup_platform_for_device(hass, mock_config_entry, Platform.SIREN, mocked_hub)

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [ENTITY_ID], ATTR_DURATION: 5, ATTR_TONE: "Foo"},
        blocking=True,
    )

    alarm_module.play.assert_called_with(volume=None, duration=5, sound="Foo")


@pytest.mark.parametrize(("duration"), [0, 301])
async def test_turn_on_with_invalid_duration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_hub: Device,
    duration: int,
) -> None:
    """Test that turn_on with invalid_duration raises an error."""

    await setup_platform_for_device(hass, mock_config_entry, Platform.SIREN, mocked_hub)

    msg = f"Invalid duration {duration} available: 1-300s"

    with pytest.raises(ServiceValidationError, match=msg):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [ENTITY_ID],
                ATTR_DURATION: duration,
            },
            blocking=True,
        )
