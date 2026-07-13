"""Test the Reolink binary sensor platform."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.reolink.const import DOMAIN
from homeassistant.components.reolink.coordinator import DEVICE_UPDATE_INTERVAL_MIN
from homeassistant.components.reolink.host import ONVIF
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import (
    TEST_CAM_NAME,
    TEST_DUO_MODEL,
    TEST_HOST_MODEL,
    TEST_NVR_NAME,
    TEST_UID,
    TEST_UID_CAM,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "reolink_host")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.reolink.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, config_entry)
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_motion_sensor(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test binary sensor entity with motion sensor."""
    reolink_host.model = TEST_DUO_MODEL
    reolink_host.motion_detected.return_value = True
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_lens_0_motion"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_host.motion_detected.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL_MIN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    # test ONVIF webhook callback
    reolink_host.motion_detected.return_value = True
    reolink_host.ONVIF_event_callback.return_value = [0]
    webhook_id = config_entry.runtime_data.host._webhook_ids[ONVIF]
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{webhook_id}", data=b"test_data")

    assert hass.states.get(entity_id).state == STATE_ON


async def test_dual_lens_sub_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dual lens camera with separate sensors per lens uses lens sub-devices."""
    reolink_host.model = TEST_DUO_MODEL
    reolink_host.is_nvr = False
    reolink_host.channels = [0, 1]
    reolink_host.stream_channels = [0, 1]
    # a Reolink Duo reports a junk name like "2" for the second channel,
    # the lens sub-device names should be based on the channel 0 name
    reolink_host.camera_name.side_effect = lambda ch: (
        TEST_CAM_NAME if ch == 0 else str(ch + 1)
    )

    # an entity of a previous version attached to the host device
    # should be moved to the lens sub-device, keeping its entity_id
    host_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, TEST_UID)},
    )
    # a lens sub-device of a previous run should be left untouched by migration
    old_lens_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, f"{TEST_UID}_lens0")},
    )
    old_entity = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{TEST_UID}_0_motion",
        suggested_object_id=f"{TEST_CAM_NAME}_motion_lens_0",
        config_entry=config_entry,
        device_id=host_device.id,
    )

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    for channel in (0, 1):
        lens_device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"{TEST_UID}_lens{channel}")}
        )
        assert lens_device is not None
        assert lens_device.name == f"{TEST_CAM_NAME} lens {channel}"
        assert lens_device.via_device_id == host_device.id

        entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_lens_{channel}_person"
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.device_id == lens_device.id

    # sensors that are not lens-specific should stay on the main device
    entity = entity_registry.async_get(
        f"{Platform.BINARY_SENSOR}.{TEST_NVR_NAME}_sleep_status"
    )
    assert entity is not None
    assert entity.device_id == host_device.id

    # the pre-existing lens sub-device and entity should have been reused
    lens_0_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_UID}_lens0")}
    )
    assert lens_0_device is not None
    assert lens_0_device.id == old_lens_device.id
    entity = entity_registry.async_get(old_entity.entity_id)
    assert entity is not None
    assert entity.device_id == lens_0_device.id


@pytest.mark.parametrize(
    ("supported", "parent_dev_id"),
    [
        pytest.param(
            lambda ch, cap: True,
            f"{TEST_UID}_{TEST_UID_CAM}",
            id="uid",
        ),
        pytest.param(
            lambda ch, cap: not (cap == "UID" and ch is not None),
            f"{TEST_UID}_ch0",
            id="no_uid",
        ),
    ],
)
async def test_dual_lens_sub_devices_nvr(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
    device_registry: dr.DeviceRegistry,
    supported: Callable[[int | None, str], bool],
    parent_dev_id: str,
) -> None:
    """Test lens sub-devices are connected to the camera device of a NVR-type host."""
    reolink_host.model = TEST_DUO_MODEL
    reolink_host.supported.side_effect = supported

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    parent_device = device_registry.async_get_device(
        identifiers={(DOMAIN, parent_dev_id)}
    )
    assert parent_device is not None
    lens_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_UID}_lens0")}
    )
    assert lens_device is not None
    assert lens_device.via_device_id == parent_device.id


async def test_smart_ai_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test smart ai binary sensor entity."""
    reolink_host.model = TEST_HOST_MODEL
    reolink_host.baichuan.smart_ai_state.return_value = True
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_crossline_zone1_person"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_host.baichuan.smart_ai_state.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL_MIN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_index_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test index binary sensor entity."""
    reolink_host.baichuan.io_inputs.return_value = [0]
    reolink_host.baichuan.io_input_state.return_value = True
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_io_input_0"
    assert hass.states.get(entity_id).state == STATE_ON

    reolink_host.baichuan.io_input_state.return_value = False
    freezer.tick(DEVICE_UPDATE_INTERVAL_MIN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_tcp_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test tcp callback using motion sensor."""

    class callback_mock_class:
        callback_func = None

        def register_callback(
            self, callback_id: str, callback: Callable[[], None], *args, **key_args
        ) -> None:
            if callback_id.endswith("_motion"):
                self.callback_func = callback

    callback_mock = callback_mock_class()

    reolink_host.model = TEST_HOST_MODEL
    reolink_host.baichuan.events_active = True
    reolink_host.baichuan.subscribe_events.reset_mock(side_effect=True)
    reolink_host.baichuan.register_callback = callback_mock.register_callback
    reolink_host.motion_detected.return_value = True

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BINARY_SENSOR}.{TEST_CAM_NAME}_motion"
    assert hass.states.get(entity_id).state == STATE_ON

    # simulate a TCP push callback
    reolink_host.motion_detected.return_value = False
    assert callback_mock.callback_func is not None
    callback_mock.callback_func()

    assert hass.states.get(entity_id).state == STATE_OFF
