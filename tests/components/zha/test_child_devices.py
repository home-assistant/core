"""Test ZHA child devices."""

from collections.abc import Callable, Coroutine
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_get_device_automations
from zha.application.gateway import (
    DeviceFullInitEvent,
    DevicePairingStatus,
    ExtendedDeviceInfoWithPairingStatus,
)
from zha.zigbee.child_device import ChildDevice
from zha.zigbee.device import Device
from zigpy.device import Device as ZigpyDevice
from zigpy.profiles import zha
from zigpy.zcl.clusters import general, security

from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.zha.const import DOMAIN
from homeassistant.components.zha.diagnostics import async_get_device_diagnostics
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    async_get_zha_device_proxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

IEEE = "01:2d:6f:00:0a:90:69:e8"


@pytest.fixture(autouse=True)
def platforms_only():
    """Only set up the required platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (Platform.BUTTON, Platform.SENSOR, Platform.SELECT, Platform.SWITCH),
    ):
        yield


def _two_gang_endpoints(*, ias_wd: bool = False) -> dict[int, dict]:
    """Return the signature of a two-socket power strip."""
    return {
        endpoint_id: {
            SIG_EP_INPUT: [
                general.Basic.cluster_id,
                general.Identify.cluster_id,
                general.OnOff.cluster_id,
                *([security.IasWd.cluster_id] if ias_wd and endpoint_id == 1 else []),
            ],
            SIG_EP_OUTPUT: [],
            SIG_EP_TYPE: zha.DeviceType.ON_OFF_PLUG_IN_UNIT,
            SIG_EP_PROFILE: zha.PROFILE_ID,
        }
        for endpoint_id in (1, 2)
    }


async def _join_device(
    hass: HomeAssistant,
    zigpy_device_mock: Callable[..., ZigpyDevice],
    *,
    model: str = "TS011F",
    ias_wd: bool = False,
) -> ZHADeviceProxy:
    """Join a two-socket power strip."""
    gateway = get_zha_gateway(hass)
    zigpy_device = zigpy_device_mock(
        _two_gang_endpoints(ias_wd=ias_wd),
        ieee=IEEE,
        manufacturer="_TZ3000_abcdefgh",
        model=model,
        node_descriptor=b"\x01@\x8e\x02\x10RR\x00\x00\x00R\x00\x00",
    )
    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    return get_zha_gateway_proxy(hass).device_proxies[zigpy_device.ieee]


async def _reinterview(hass: HomeAssistant, device_proxy: ZHADeviceProxy) -> None:
    """Re-interview a device, rebuilding the same ZHA device object."""
    zha_device = device_proxy.device
    await get_zha_gateway(hass)._async_device_reinterviewed(zha_device.device)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert device_proxy.device is zha_device


def _switch_entity_ids(entity_registry: er.EntityRegistry) -> list[str]:
    """Return the entity ids of the switches, in endpoint order."""
    entity_ids = []
    for endpoint_id in (1, 2):
        entity_id = entity_registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, f"{IEEE}-{endpoint_id}"
        )
        assert entity_id is not None
        entity_ids.append(entity_id)
    return entity_ids


async def test_child_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigpyDevice],
) -> None:
    """Test the outputs of a power strip are child devices."""
    await setup_zha()
    device_proxy = await _join_device(hass, zigpy_device_mock)

    parent = device_registry.async_get(device_proxy.device_id)
    assert parent is not None
    assert parent.identifiers == {(DOMAIN, IEEE)}

    children = sorted(
        dr.async_entries_for_parent_device(device_registry, parent.id),
        key=lambda child: child.name or "",
    )
    assert [(child.name, child.identifiers) for child in children] == [
        ("Channel 1", {(DOMAIN, f"{IEEE}-1")}),
        ("Channel 2", {(DOMAIN, f"{IEEE}-2")}),
    ]

    # Each output is the primary entity of its child device
    switch_entity_ids = _switch_entity_ids(entity_registry)
    for entity_id, child in zip(switch_entity_ids, children, strict=True):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == child.id
        assert entry.original_name is None

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.name == child.name

    # Device level entities stay on the main device
    lqi_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{IEEE}-1-0-lqi"
    )
    assert lqi_entity_id is not None
    lqi_entry = entity_registry.async_get(lqi_entity_id)
    assert lqi_entry is not None
    assert lqi_entry.device_id == parent.id

    # A child device resolves to its ZHA device
    assert async_get_zha_device_proxy(hass, children[0].id) is device_proxy

    # Its diagnostics are those of the ZHA device
    diagnostics = await async_get_device_diagnostics(
        hass, device_proxy.gateway_proxy.config_entry, children[0]
    )
    assert diagnostics["model"] == "TS011F"
    assert [child["id"] for child in diagnostics["child_devices"]] == ["1", "2"]


async def test_not_allowlisted(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigpyDevice],
) -> None:
    """Test a device that is not allowlisted keeps all entities on its device."""
    await setup_zha()
    device_proxy = await _join_device(hass, zigpy_device_mock, model="FakeModel")

    assert not dr.async_entries_for_parent_device(
        device_registry, device_proxy.device_id
    )
    for entity_id in _switch_entity_ids(entity_registry):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == device_proxy.device_id


@pytest.mark.parametrize(
    ("translation_key", "translation_placeholders", "expected_name"),
    [
        # Translated in HA
        ("channel", {"index": "7"}, "Channel 7"),
        ("left", None, "Left"),
        ("right", None, "Right"),
        ("top", None, "Top"),
        ("bottom", None, "Bottom"),
        ("valve", {"index": "2"}, "Valve 2"),
        # A custom quirk with a new translation key uses the fallback name
        ("custom_key", None, "Fallback"),
        (None, None, "Fallback"),
    ],
)
async def test_child_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigpyDevice],
    translation_key: str | None,
    translation_placeholders: dict[str, str] | None,
    expected_name: str,
) -> None:
    """Test the name of a child device defined by a quirk."""
    child_devices = (
        ChildDevice(
            id="custom",
            endpoint_ids=frozenset({2}),
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
            fallback_name="Fallback",
        ),
    )

    await setup_zha()
    with patch.object(Device, "_quirk_child_devices", return_value=child_devices):
        device_proxy = await _join_device(hass, zigpy_device_mock)

    (child,) = dr.async_entries_for_parent_device(
        device_registry, device_proxy.device_id
    )
    assert child.identifiers == {(DOMAIN, f"{IEEE}-custom")}
    assert child.name == expected_name


async def test_reconcile_child_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigpyDevice],
) -> None:
    """Test entities follow child devices that are added and removed."""
    await setup_zha()

    with patch("zha.zigbee.device.is_child_device_allowlisted", return_value=False):
        device_proxy = await _join_device(hass, zigpy_device_mock)

    parent_id = device_proxy.device_id
    switch_1, switch_2 = _switch_entity_ids(entity_registry)

    # Disabled entities follow their child device as well
    entity_registry.async_update_entity(
        switch_2, disabled_by=er.RegistryEntryDisabler.USER
    )
    entity_registry.async_update_entity(switch_1, name="Kettle")
    await _reinterview(hass, device_proxy)
    assert device_proxy.device.child_devices

    children = {
        next(iter(child.identifiers))[1]: child
        for child in dr.async_entries_for_parent_device(device_registry, parent_id)
    }
    assert set(children) == {f"{IEEE}-1", f"{IEEE}-2"}

    entry_1 = entity_registry.async_get(switch_1)
    entry_2 = entity_registry.async_get(switch_2)
    assert entry_1 is not None
    assert entry_2 is not None
    assert entry_1.device_id == children[f"{IEEE}-1"].id
    assert entry_2.device_id == children[f"{IEEE}-2"].id
    assert entry_2.disabled_by is er.RegistryEntryDisabler.USER

    # The user disables a child device, which disables its entity
    device_registry.async_update_child_device(
        children[f"{IEEE}-1"].id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done()
    entry_1 = entity_registry.async_get(switch_1)
    assert entry_1 is not None
    assert entry_1.disabled_by is er.RegistryEntryDisabler.DEVICE

    # The child devices go away (e.g. after a re-interview): the entities move back to
    # the main device, keeping their entity ID and customizations, and the empty
    # child devices are removed
    with patch("zha.zigbee.device.is_child_device_allowlisted", return_value=False):
        await _reinterview(hass, device_proxy)
    assert not device_proxy.device.child_devices

    assert not dr.async_entries_for_parent_device(device_registry, parent_id)
    entry_1 = entity_registry.async_get(switch_1)
    entry_2 = entity_registry.async_get(switch_2)
    assert entry_1 is not None
    assert entry_2 is not None
    assert entry_1.device_id == parent_id
    assert entry_1.name == "Kettle"
    # The entity is no longer disabled along with the removed child device
    assert entry_1.disabled_by is None
    assert entry_2.device_id == parent_id
    assert entry_2.disabled_by is er.RegistryEntryDisabler.USER


async def test_child_device_automations(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigpyDevice],
) -> None:
    """Test device triggers and actions belong to the main device only."""
    await setup_zha()
    device_proxy = await _join_device(hass, zigpy_device_mock, ias_wd=True)
    device_proxy.device._zigpy_device.device_automation_triggers = {
        ("remote_button_short_press", "button_1"): {"command": "on"}
    }

    child, _ = dr.async_entries_for_parent_device(
        device_registry, device_proxy.device_id
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_proxy.device_id
    )
    assert any(trigger["domain"] == DOMAIN for trigger in triggers)
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, device_proxy.device_id
    )
    assert any(action["domain"] == DOMAIN for action in actions)

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, child.id
    )
    assert not any(trigger["domain"] == DOMAIN for trigger in triggers)
    actions = await async_get_device_automations(
        hass, DeviceAutomationType.ACTION, child.id
    )
    assert not any(action["domain"] == DOMAIN for action in actions)

    # The device joined after ZHA started, so it isn't in the trigger cache. Listing
    # the triggers of its child device still works after ZHA is unloaded.
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, child.id
    )
    assert not any(trigger["domain"] == DOMAIN for trigger in triggers)


async def test_disable_entity_on_child_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigpyDevice],
) -> None:
    """Test disabling an entity on a child device disables the ZHA entity."""
    await setup_zha()
    device_proxy = await _join_device(hass, zigpy_device_mock)
    _, switch_2 = _switch_entity_ids(entity_registry)
    zha_entity = device_proxy.device.platform_entities[(Platform.SWITCH, f"{IEEE}-2")]
    assert zha_entity.enabled

    entity_registry.async_update_entity(
        switch_2, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert not zha_entity.enabled


async def test_reinterview_same_device_object(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigpyDevice],
) -> None:
    """Test child devices are reconciled when a re-interview keeps the device object."""
    await setup_zha()
    gateway_proxy = get_zha_gateway_proxy(hass)
    device_proxy = await _join_device(hass, zigpy_device_mock)
    parent_id = device_proxy.device_id
    switch_1, _ = _switch_entity_ids(entity_registry)

    child_1 = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{IEEE}-1"), gateway_proxy.config_entry.entry_id
    )
    assert child_1 is not None
    device_registry.async_update_child_device(
        child_1.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entry = entity_registry.async_get(switch_1)
    assert entry is not None
    assert entry.device_id == child_1.id
    assert entry.disabled_by is er.RegistryEntryDisabler.DEVICE

    with patch("zha.zigbee.device.is_child_device_allowlisted", return_value=False):
        await device_proxy.device.recompute_entities()

    gateway_proxy.handle_device_fully_initialized(
        DeviceFullInitEvent(
            device_info=ExtendedDeviceInfoWithPairingStatus(
                pairing_status=DevicePairingStatus.CONFIGURED,
                **device_proxy.device.extended_device_info.__dict__,
            )
        )
    )

    assert not dr.async_entries_for_parent_device(device_registry, parent_id)
    entry = entity_registry.async_get(switch_1)
    assert entry is not None
    assert entry.device_id == parent_id
    assert entry.disabled_by is None
