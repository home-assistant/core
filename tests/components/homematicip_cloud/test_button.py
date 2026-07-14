"""Tests for HomematicIP Cloud button."""

from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .helper import HomeFactory, get_and_check_entity_basics


async def test_hmip_garage_door_controller_button(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test HomematicipGarageDoorControllerButton."""
    entity_id = "button.garagentor"
    entity_name = "Garagentor"
    device_model = "HmIP-WGC"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )

    get_and_check_entity_basics(hass, mock_hap, entity_id, entity_name, device_model)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    freezer.move_to(now)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == now.isoformat()


async def test_hmip_full_flush_lock_controller_button(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    default_mock_hap_factory: HomeFactory,
    full_flush_lock_controller_device_data: dict[str, Any],
) -> None:
    """Test HomematicIP full flush lock controller opener button.

    The button must pull the latch on the ACCESS_AUTHORIZATION_CHANNEL with
    role DOOR_OPENER_ACTUATOR (channel 9 in the fixture), not call
    send_start_impulse on the underlying DOOR_SWITCH_CHANNEL. The former is
    the only endpoint non-admin clients are allowed to invoke; the latter
    fails with CLIENT_ACCESS_DENIED for non-admin clients.
    """
    entity_id = "button.universal_motorschloss_controller_door_opener"
    entity_name = "Universal Motorschloss Controller Door opener"
    device_model = "HmIP-FLC"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universal Motorschloss Controller"],
        extra_devices=[full_flush_lock_controller_device_data],
    )

    get_and_check_entity_basics(hass, mock_hap, entity_id, entity_name, device_model)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    auth_channel = next(
        ch
        for ch in hmip_device.functionalChannels
        if ch.functionalChannelType.name == "ACCESS_AUTHORIZATION_CHANNEL"
        and ch.channelRole == "DOOR_OPENER_ACTUATOR"
    )

    with (
        patch.object(
            auth_channel, "async_pull_latch", new_callable=AsyncMock
        ) as mock_pull_latch,
        patch.object(
            hmip_device, "send_start_impulse_async", new_callable=AsyncMock
        ) as mock_send_start_impulse,
    ):
        now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
        freezer.move_to(now)
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    mock_pull_latch.assert_awaited_once_with()
    mock_send_start_impulse.assert_not_awaited()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == now.isoformat()


async def test_hmip_full_flush_lock_controller_button_missing_channel(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    full_flush_lock_controller_device_data: dict[str, Any],
) -> None:
    """Button is not created when the door-opener auth channel is missing."""
    # Strip the access-authorization channel for DOOR_OPENER_ACTUATOR so the
    # setup detection function rejects the device.
    full_flush_lock_controller_device_data["functionalChannels"].pop("9")
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universal Motorschloss Controller"],
        extra_devices=[full_flush_lock_controller_device_data],
    )

    entity_id = "button.universal_motorschloss_controller_door_opener"
    assert hass.states.get(entity_id) is None
    assert entity_id not in mock_hap.hmip_device_by_entity_id
