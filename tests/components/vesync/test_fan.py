"""Tests for the fan module."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest
import requests_mock
from syrupy import SnapshotAssertion

from homeassistant.components.fan import ATTR_PRESET_MODE, DOMAIN as FAN_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_FAN, mock_devices_response

from tests.common import MockConfigEntry

NoException = nullcontext()


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_fan_state(
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
        if entity.domain == FAN_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, "pyvesync.vesyncfan.VeSyncTowerFan.turn_on"),
        (SERVICE_TURN_OFF, "pyvesync.vesyncfan.VeSyncTowerFan.turn_off"),
    ],
)
async def test_turn_on_off_success(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off method."""

    with (
        patch(command, return_value=True) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.schedule_update_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                action,
                {ATTR_ENTITY_ID: ENTITY_FAN},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, "pyvesync.vesyncfan.VeSyncTowerFan.turn_on"),
        (SERVICE_TURN_OFF, "pyvesync.vesyncfan.VeSyncTowerFan.turn_off"),
    ],
)
async def test_turn_on_off_raises_error(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off raises errors when fails."""

    # returns False indicating failure in which case raises HomeAssistantError.
    with (
        patch(
            command,
            return_value=False,
        ) as method_mock,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_FAN},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
) -> None:
    """Test handling of value in set_preset_mode method. Does this via turn on as it increases test coverage."""

    # If VeSyncTowerFan.normal_mode fails (returns False), then HomeAssistantError is raised
    with (
        expectation,
        patch(
            "pyvesync.vesyncfan.VeSyncTowerFan.normal_mode",
            return_value=api_response,
        ) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.schedule_update_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_PRESET_MODE: "normal"},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()
