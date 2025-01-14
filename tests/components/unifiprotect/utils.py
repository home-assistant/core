"""Test helpers for UniFi Protect."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import Mock

from uiprotect import ProtectApiClient
from uiprotect.data import (
    Bootstrap,
    Camera,
    Event,
    EventType,
    ModelType,
    ProtectAdoptableDeviceModel,
    WSSubscriptionMessage,
)
from uiprotect.data.bootstrap import ProtectDeviceRef
from uiprotect.test_util.anonymize import random_hex
from uiprotect.websocket import WebsocketState

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityDescription
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@dataclass
class MockUFPFixture:
    """Mock for NVR."""

    entry: MockConfigEntry
    api: ProtectApiClient
    ws_subscription: Callable[[WSSubscriptionMessage], None] | None = None
    ws_state_subscription: Callable[[WebsocketState], None] | None = None

    def ws_msg(self, msg: WSSubscriptionMessage) -> None:
        """Emit WS message for testing."""

        if self.ws_subscription is not None:
            self.ws_subscription(msg)


def reset_objects(bootstrap: Bootstrap):
    """Reset bootstrap objects."""

    bootstrap.cameras = {}
    bootstrap.lights = {}
    bootstrap.sensors = {}
    bootstrap.viewers = {}
    bootstrap.events = {}
    bootstrap.doorlocks = {}
    bootstrap.chimes = {}


async def time_changed(hass: HomeAssistant, seconds: int) -> None:
    """Trigger time changed."""
    next_update = dt_util.utcnow() + timedelta(seconds)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()


async def enable_entity(
    hass: HomeAssistant, entry_id: str, entity_id: str
) -> er.RegistryEntry:
    """Enable a disabled entity."""
    entity_registry = er.async_get(hass)

    updated_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert not updated_entity.disabled
    await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()

    return updated_entity


def assert_entity_counts(
    hass: HomeAssistant, platform: Platform, total: int, enabled: int
) -> None:
    """Assert entity counts for a given platform."""

    entity_registry = er.async_get(hass)

    entities = [
        e for e in entity_registry.entities if split_entity_id(e)[0] == platform.value
    ]

    assert len(entities) == total
    assert len(hass.states.async_all(platform.value)) == enabled


def normalize_name(name: str) -> str:
    """Normalize name."""

    return name.lower().replace(":", "").replace(" ", "_").replace("-", "_")


def ids_from_device_description(
    platform: Platform,
    device: ProtectAdoptableDeviceModel,
    description: EntityDescription,
) -> tuple[str, str]:
    """Return expected unique_id and entity_id for a give platform/device/description combination."""

    entity_name = normalize_name(device.display_name)

    if description.name and isinstance(description.name, str):
        description_entity_name = normalize_name(description.name)
    else:
        description_entity_name = normalize_name(description.key)

    unique_id = f"{device.mac}_{description.key}"
    entity_id = f"{platform.value}.{entity_name}_{description_entity_name}"

    return unique_id, entity_id


def generate_random_ids() -> tuple[str, str]:
    """Generate random IDs for device."""

    return random_hex(24).lower(), random_hex(12).upper()


def regenerate_device_ids(device: ProtectAdoptableDeviceModel) -> None:
    """Regenerate the IDs on UFP device."""

    device.id, device.mac = generate_random_ids()


def add_device_ref(bootstrap: Bootstrap, device: ProtectAdoptableDeviceModel) -> None:
    """Manually add device ref to bootstrap for lookup."""

    ref = ProtectDeviceRef(id=device.id, model=device.model)
    bootstrap.id_lookup[device.id] = ref
    bootstrap.mac_lookup[device.mac.lower()] = ref


def add_device(
    bootstrap: Bootstrap, device: ProtectAdoptableDeviceModel, regenerate_ids: bool
) -> None:
    """Add test device to bootstrap."""

    if device.model is None:
        return

    device._api = bootstrap.api
    if isinstance(device, Camera):
        for channel in device.channels:
            channel._api = bootstrap.api

    if regenerate_ids:
        regenerate_device_ids(device)

    devices = getattr(bootstrap, f"{device.model.value}s")
    devices[device.id] = device
    add_device_ref(bootstrap, device)


async def init_entry(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    devices: Sequence[ProtectAdoptableDeviceModel],
    regenerate_ids: bool = True,
    debug: bool = False,
) -> None:
    """Initialize Protect entry with given devices."""

    reset_objects(ufp.api.bootstrap)
    for device in devices:
        add_device(ufp.api.bootstrap, device, regenerate_ids)

    if debug:
        assert await async_setup_component(hass, "logger", {"logger": {}})
        await hass.services.async_call(
            "logger",
            "set_level",
            {"homeassistant.components.unifiprotect": "DEBUG"},
            blocking=True,
        )
    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()


async def remove_entities(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    ufp_devices: list[ProtectAdoptableDeviceModel],
) -> None:
    """Remove all entities for given Protect devices."""

    for ufp_device in ufp_devices:
        if not ufp_device.is_adopted_by_us:
            continue

        devices = getattr(ufp.api.bootstrap, f"{ufp_device.model.value}s")
        del devices[ufp_device.id]

        mock_msg = Mock()
        mock_msg.changed_data = {}
        mock_msg.old_obj = ufp_device
        mock_msg.new_obj = None
        ufp.ws_msg(mock_msg)

    await time_changed(hass, 30)


async def adopt_devices(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    ufp_devices: list[ProtectAdoptableDeviceModel],
    fully_adopt: bool = False,
):
    """Emit WS to re-adopt give Protect devices."""

    for ufp_device in ufp_devices:
        if fully_adopt:
            ufp_device.is_adopted = True
            ufp_device.is_adopted_by_other = False
            ufp_device.can_adopt = False

        devices = getattr(ufp.api.bootstrap, f"{ufp_device.model.value}s")
        devices[ufp_device.id] = ufp_device

        mock_msg = Mock()
        mock_msg.changed_data = {}
        mock_msg.new_obj = Event(
            api=ufp_device.api,
            id=random_hex(24),
            smart_detect_types=[],
            smart_detect_event_ids=[],
            type=EventType.DEVICE_ADOPTED,
            start=dt_util.utcnow(),
            score=100,
            metadata={"device_id": ufp_device.id},
            model=ModelType.EVENT,
        )
        ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()
