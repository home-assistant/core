"""Tests for automatic LG webOS TV wake-up."""

from unittest.mock import Mock

from aiowebostv import WebOsTvConnectionError, WebOsTvWakeError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import automation
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.webostv.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import ENTITY_ID, FAKE_UUID
from .test_media_player import mock_scan_interval

MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"


async def test_wake_after_restart(
    hass: HomeAssistant,
    client: Mock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Use persisted registry addresses while the TV is unreachable at startup."""
    entry = await setup_webostv(hass)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FAKE_UUID), entry.entry_id
    )
    assert device is not None
    device_registry.async_update_device(
        device.id, new_connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}
    )
    client.mac_addresses = {}
    client.tv_state.is_on = False
    client.is_connected.return_value = False
    client.connect.side_effect = WebOsTvConnectionError
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await mock_scan_interval(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert (
        hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.TURN_ON
    )
    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    client.turn_on.assert_awaited_once_with([MAC_ADDRESS])


async def test_discover_mac(
    hass: HomeAssistant, client: Mock, freezer: FrozenDateTimeFactory
) -> None:
    """Enable wake-up after a TV without saved MACs connects."""
    client.mac_addresses = {}
    client.is_connected.return_value = False
    await setup_webostv(hass)
    assert (
        not hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.TURN_ON
    )
    client.mac_addresses = {"wired": MAC_ADDRESS}
    await mock_scan_interval(hass, freezer)
    assert (
        hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.TURN_ON
    )
    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    client.turn_on.assert_awaited_once_with([MAC_ADDRESS])


async def test_no_mac_unavailable(
    hass: HomeAssistant, client: Mock, freezer: FrozenDateTimeFactory
) -> None:
    """Without a MAC or automation, an unreachable TV remains unavailable."""
    client.mac_addresses = {}
    await setup_webostv(hass)
    client.is_connected.return_value = False
    client.connect.side_effect = WebOsTvConnectionError
    await mock_scan_interval(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "macs",
    [
        pytest.param({}, id="no-mac"),
        pytest.param({"wired": MAC_ADDRESS}, id="known-mac"),
    ],
)
async def test_automation_priority(
    hass: HomeAssistant,
    client: Mock,
    service_calls: list[ServiceCall],
    macs: dict[str, str],
) -> None:
    """Always prefer the user's turn-on automation."""
    client.mac_addresses = macs
    await setup_webostv(hass)
    client.tv_state.is_on = False
    await client.mock_state_update()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "triggers": [
                        {"trigger": "webostv.turn_on", "entity_id": ENTITY_ID}
                    ],
                    "actions": [{"action": "test.automation"}],
                }
            ]
        },
    )
    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert service_calls[-1].service == "automation"
    client.turn_on.assert_not_awaited()


async def test_wake_error(hass: HomeAssistant, client: Mock) -> None:
    """Translate a library wake-up error for the action caller."""
    client.mac_addresses = {"wired": MAC_ADDRESS}
    await setup_webostv(hass)
    client.tv_state.is_on = False
    client.turn_on.side_effect = WebOsTvWakeError
    await client.mock_state_update()
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert err.value.translation_key == "wake_failed"
