"""Test the Heiman Local switch and config entry lifecycle."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.heiman_local.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import WiFiSwitch

MAC = "a8c1d6010203"
ENTITY_ID = "switch.heiman_wifi_switch"


async def test_switch_lifecycle(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: WiFiSwitch,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Register one switch, send commands, then recover after a polling error."""
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == MAC
    assert entry.data == device.address
    assert [state.entity_id for state in hass.states.async_all(SWITCH_DOMAIN)] == [
        ENTITY_ID
    ]
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == MAC
    registered = device_registry.async_get(entity.device_id)
    assert registered.identifiers == {(DOMAIN, MAC)}
    assert registered.connections == {(dr.CONNECTION_NETWORK_MAC, "a8:c1:d6:01:02:03")}

    for action, expected in (
        (SERVICE_TURN_ON, STATE_ON),
        (SERVICE_TURN_OFF, STATE_OFF),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN, action, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
        assert hass.states.get(ENTITY_ID).state == expected
    assert device.received == [
        {"property": "power", "value": True},
        {"property": "power", "value": False},
    ]

    device.online = False
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    device.online = True
    device.flat_state = True
    device.power = True
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.usefixtures("entry")
async def test_poll_rejects_reused_address(
    hass: HomeAssistant, device: WiFiSwitch, freezer: FrozenDateTimeFactory
) -> None:
    """Ignore a different switch assigned the configured IP address."""
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    original_mac = device.mac
    device.mac = "A8:C1:D6:04:05:06"
    device.flat_state = True
    device.power = True
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    device.mac = original_mac
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("attribute", "value", "command_count"),
    [
        pytest.param("reject_command", True, 1, id="rejected"),
        pytest.param("apply_command", False, 1, id="readback-mismatch"),
        pytest.param("mac", "A8:C1:D6:04:05:06", 0, id="different-mac"),
    ],
)
async def test_command_failure(
    hass: HomeAssistant,
    device: WiFiSwitch,
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    value: bool | str,
    command_count: int,
) -> None:
    """Expose failed commands and retain the confirmed state."""
    monkeypatch.setattr(device, attribute, value)
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert exc.value.translation_key == "set_power_failed"
    assert len(device.received) == command_count
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_retry_setup(
    hass: HomeAssistant, device: WiFiSwitch, freezer: FrozenDateTimeFactory
) -> None:
    """Retry setup if the stored switch does not answer the first status request."""
    device.online = False
    entry = MockConfigEntry(domain=DOMAIN, data=device.address, unique_id=MAC)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get(ENTITY_ID) is None

    device.online = True
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
