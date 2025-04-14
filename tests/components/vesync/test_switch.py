"""Tests for the switch module."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest
import requests_mock
from syrupy import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_SWITCH_DISPLAY, mock_devices_response

from tests.common import MockConfigEntry

NoException = nullcontext()


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_switch_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    requests_mock: requests_mock.Mocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(requests_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == SWITCH_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, "pyvesync.vesyncfan.VeSyncHumid200300S.turn_on_display"),
        (SERVICE_TURN_OFF, "pyvesync.vesyncfan.VeSyncHumid200300S.turn_off_display"),
    ],
)
async def test_turn_on_off_display_success(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    action: str,
    command: str,
) -> None:
    """Test switch turn on and off command with success response."""

    with (
        patch(
            command,
            return_value=True,
        ) as method_mock,
        patch(
            "homeassistant.components.vesync.switch.VeSyncSwitchEntity.schedule_update_ha_state"
        ) as update_mock,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_SWITCH_DISPLAY},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()
    update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, "pyvesync.vesyncfan.VeSyncHumid200300S.turn_on_display"),
        (SERVICE_TURN_OFF, "pyvesync.vesyncfan.VeSyncHumid200300S.turn_off_display"),
    ],
)
async def test_turn_on_off_display_raises_error(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    action: str,
    command: str,
) -> None:
    """Test switch turn on and off command raises HomeAssistantError."""

    with (
        patch(
            command,
            return_value=False,
        ) as method_mock,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_SWITCH_DISPLAY},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()
