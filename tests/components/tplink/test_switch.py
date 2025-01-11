"""Tests for switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from kasa import AuthenticationError, Device, KasaException, Module, TimeoutError
from kasa.iot import IotStrip
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import tplink
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.components.tplink.entity import EXCLUDED_FEATURES
from homeassistant.components.tplink.switch import SWITCH_DESCRIPTIONS
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify

from . import (
    DEVICE_ID,
    MAC_ADDRESS,
    _mocked_device,
    _mocked_strip_children,
    _patch_connect,
    _patch_discovery,
    setup_platform_for_device,
    snapshot_platform,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a sensor unique ids."""
    features = {description.key for description in SWITCH_DESCRIPTIONS}
    features.update(EXCLUDED_FEATURES)
    device = _mocked_device(alias="my_device", features=features)

    await setup_platform_for_device(hass, mock_config_entry, Platform.SWITCH, device)
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )

    for excluded in EXCLUDED_FEATURES:
        assert hass.states.get(f"sensor.my_device_{excluded}") is None


async def test_plug(hass: HomeAssistant) -> None:
    """Test a smart plug."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_device(alias="my_plug", features=["state"])
    feat = plug.features["state"]
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    feat.set_value.assert_called_once()
    feat.set_value.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    feat.set_value.assert_called_once()
    feat.set_value.reset_mock()


@pytest.mark.parametrize(
    ("dev", "domain"),
    [
        (_mocked_device(alias="my_plug", features=["state", "led"]), "switch"),
        (
            _mocked_device(
                alias="my_strip",
                features=["state", "led"],
                children=_mocked_strip_children(),
            ),
            "switch",
        ),
        (
            _mocked_device(
                alias="my_light", modules=[Module.Light], features=["state", "led"]
            ),
            "light",
        ),
    ],
)
async def test_led_switch(hass: HomeAssistant, dev: Device, domain: str) -> None:
    """Test LED setting for plugs, strips and dimmers."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    feat = dev.features["led"]
    already_migrated_config_entry.add_to_hass(hass)
    with _patch_discovery(device=dev), _patch_connect(device=dev):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_name = slugify(dev.alias)

    led_entity_id = f"switch.{entity_name}_led"
    led_state = hass.states.get(led_entity_id)
    assert led_state.state == STATE_ON
    assert led_state.name == f"{dev.alias} LED"

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: led_entity_id}, blocking=True
    )
    feat.set_value.assert_called_once_with(False)
    feat.set_value.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: led_entity_id}, blocking=True
    )
    feat.set_value.assert_called_once_with(True)
    feat.set_value.reset_mock()


async def test_plug_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a plug unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_device(alias="my_plug", features=["state", "led"])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    assert entity_registry.async_get(entity_id).unique_id == DEVICE_ID


async def test_plug_update_fails(hass: HomeAssistant) -> None:
    """Test a smart plug update failure."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_device(alias="my_plug", features=["state", "led"])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    plug.update = AsyncMock(side_effect=KasaException)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE


async def test_strip(hass: HomeAssistant) -> None:
    """Test a smart strip."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_device(
        alias="my_strip",
        children=_mocked_strip_children(features=["state"]),
        features=["state", "led"],
        spec=IotStrip,
    )
    strip.children[0].features["state"].value = True
    strip.children[1].features["state"].value = False
    with _patch_discovery(device=strip), _patch_connect(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_strip_plug0"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    feat = strip.children[0].features["state"]
    feat.set_value.assert_called_once()
    feat.set_value.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    feat.set_value.assert_called_once()
    feat.set_value.reset_mock()

    entity_id = "switch.my_strip_plug1"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    feat = strip.children[1].features["state"]
    feat.set_value.assert_called_once()
    feat.set_value.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    feat.set_value.assert_called_once()
    feat.set_value.reset_mock()


async def test_strip_unique_ids(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a strip unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_device(
        alias="my_strip",
        children=_mocked_strip_children(features=["state"]),
        features=["state", "led"],
    )
    with _patch_discovery(device=strip), _patch_connect(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    for plug_id in range(2):
        entity_id = f"switch.my_strip_plug{plug_id}"
        assert (
            entity_registry.async_get(entity_id).unique_id == f"PLUG{plug_id}DEVICEID"
        )


async def test_strip_blank_alias(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a strip unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_device(
        alias="",
        model="KS123",
        children=_mocked_strip_children(features=["state", "led"], alias=""),
        features=["state", "led"],
    )
    with _patch_discovery(device=strip), _patch_connect(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    strip_entity_id = "switch.unnamed_ks123"
    state = hass.states.get(strip_entity_id)
    assert state.name == "Unnamed KS123"
    reg_ent = entity_registry.async_get(strip_entity_id)
    assert reg_ent
    reg_dev = device_registry.async_get(reg_ent.device_id)
    assert reg_dev
    assert reg_dev.name == "Unnamed KS123"

    for plug_id in range(2):
        entity_id = f"switch.unnamed_ks123_stripsocket_{plug_id + 1}"
        state = hass.states.get(entity_id)
        assert state.name == f"Unnamed KS123 Stripsocket {plug_id + 1}"

        reg_ent = entity_registry.async_get(entity_id)
        assert reg_ent
        reg_dev = device_registry.async_get(reg_ent.device_id)
        assert reg_dev
        # Switch is a primary feature so entities go on the parent device.
        assert reg_dev.name == "Unnamed KS123"


@pytest.mark.parametrize(
    ("exception_type", "msg", "reauth_expected"),
    [
        (
            AuthenticationError,
            "Device authentication error async_turn_on: test error",
            True,
        ),
        (
            TimeoutError,
            "Timeout communicating with the device async_turn_on: test error",
            False,
        ),
        (
            KasaException,
            "Unable to communicate with the device async_turn_on: test error",
            False,
        ),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
async def test_plug_errors_when_turned_on(
    hass: HomeAssistant,
    exception_type,
    msg,
    reauth_expected,
) -> None:
    """Tests the plug wraps errors correctly."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_device(alias="my_plug", features=["state", "led"])
    feat = plug.features["state"]
    feat.set_value.side_effect = exception_type("test error")

    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"

    assert not any(
        already_migrated_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    )

    with pytest.raises(HomeAssistantError, match=msg):
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    await hass.async_block_till_done()
    assert feat.set_value.call_count == 1
    assert (
        any(
            flow
            for flow in already_migrated_config_entry.async_get_active_flows(
                hass, {SOURCE_REAUTH}
            )
            if flow["handler"] == tplink.DOMAIN
        )
        == reauth_expected
    )
