"""Tests for HomematicIP Cloud locks."""

from unittest.mock import patch

from homematicip.base.enums import LockState, MotorState
import pytest

from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.components.lock import (
    DOMAIN,
    STATE_LOCKING,
    STATE_UNLOCKING,
    LockEntityFeature,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .helper import async_manipulate_test_data, get_and_check_entity_basics


async def test_manually_configured_platform(hass: HomeAssistant) -> None:
    """Test that we do not set up an access point."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"platform": HMIPC_DOMAIN}}
    )
    assert not hass.data.get(HMIPC_DOMAIN)


async def test_hmip_doorlockdrive(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipDoorLockDrive."""
    entity_id = "lock.haustuer"
    entity_name = "Haustuer"
    device_model = "HmIP-DLD"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.attributes[ATTR_SUPPORTED_FEATURES] == LockEntityFeature.OPEN

    await hass.services.async_call(
        "lock",
        "open",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert hmip_device.mock_calls[-1][0] == "set_lock_state"
    assert hmip_device.mock_calls[-1][1] == (LockState.OPEN,)

    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert hmip_device.mock_calls[-1][0] == "set_lock_state"
    assert hmip_device.mock_calls[-1][1] == (LockState.LOCKED,)

    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert hmip_device.mock_calls[-1][0] == "set_lock_state"
    assert hmip_device.mock_calls[-1][1] == (LockState.UNLOCKED,)

    await async_manipulate_test_data(
        hass, hmip_device, "motorState", MotorState.CLOSING
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_LOCKING

    await async_manipulate_test_data(
        hass, hmip_device, "motorState", MotorState.OPENING
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNLOCKING


async def test_hmip_doorlockdrive_handle_errors(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipDoorLockDrive."""
    entity_id = "lock.haustuer"
    entity_name = "Haustuer"
    device_model = "HmIP-DLD"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )
    with patch(
        "homematicip.aio.device.AsyncDoorLockDrive.set_lock_state",
        return_value={
            "errorCode": "INVALID_NUMBER_PARAMETER_VALUE",
            "minValue": 0.0,
            "maxValue": 1.01,
        },
    ):
        get_and_check_entity_basics(
            hass, mock_hap, entity_id, entity_name, device_model
        )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "lock",
                "open",
                {"entity_id": entity_id},
                blocking=True,
            )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "lock",
                "lock",
                {"entity_id": entity_id},
                blocking=True,
            )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "lock",
                "unlock",
                {"entity_id": entity_id},
                blocking=True,
            )
