"""Test the Reolink init."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from reolink_aio.api import Chime
from reolink_aio.exceptions import CredentialsInvalidError, ReolinkError

from homeassistant.components.reolink import (
    DEVICE_UPDATE_INTERVAL,
    FIRMWARE_UPDATE_INTERVAL,
    NUM_CRED_ERRORS,
)
from homeassistant.components.reolink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT, STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    TEST_CAM_MODEL,
    TEST_HOST_MODEL,
    TEST_MAC,
    TEST_NVR_NAME,
    TEST_PORT,
    TEST_UID,
    TEST_UID_CAM,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

pytestmark = pytest.mark.usefixtures("reolink_connect", "reolink_platforms")

CHIME_MODEL = "Reolink Chime"


async def test_wait(*args, **key_args) -> None:
    """Ensure a mocked function takes a bit of time to be able to timeout in test."""
    await asyncio.sleep(0)


@pytest.mark.parametrize(
    ("attr", "value", "expected"),
    [
        (
            "is_admin",
            False,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "get_host_data",
            AsyncMock(side_effect=ReolinkError("Test error")),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "get_host_data",
            AsyncMock(side_effect=ValueError("Test error")),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "get_states",
            AsyncMock(side_effect=ReolinkError("Test error")),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "get_host_data",
            AsyncMock(side_effect=CredentialsInvalidError("Test error")),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "supported",
            Mock(return_value=False),
            ConfigEntryState.LOADED,
        ),
    ],
)
async def test_failures_parametrized(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
    attr: str,
    value: Any,
    expected: ConfigEntryState,
) -> None:
    """Test outcomes when changing errors."""
    original = getattr(reolink_connect, attr)
    setattr(reolink_connect, attr, value)
    assert await hass.config_entries.async_setup(config_entry.entry_id) is (
        expected is ConfigEntryState.LOADED
    )
    await hass.async_block_till_done()

    assert config_entry.state == expected

    setattr(reolink_connect, attr, original)


async def test_firmware_error_twice(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test when the firmware update fails 2 times."""
    reolink_connect.check_new_firmware.side_effect = ReolinkError("Test error")
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.UPDATE]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.UPDATE}.{TEST_NVR_NAME}_firmware"
    assert hass.states.get(entity_id).state == STATE_OFF

    freezer.tick(FIRMWARE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    reolink_connect.check_new_firmware.reset_mock(side_effect=True)


async def test_credential_error_three(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test when the update gives credential error 3 times."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    reolink_connect.get_states.side_effect = CredentialsInvalidError("Test error")

    issue_id = f"config_entry_reauth_{DOMAIN}_{config_entry.entry_id}"
    for _ in range(NUM_CRED_ERRORS):
        assert (HOMEASSISTANT_DOMAIN, issue_id) not in issue_registry.issues
        freezer.tick(DEVICE_UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert (HOMEASSISTANT_DOMAIN, issue_id) in issue_registry.issues

    reolink_connect.get_states.reset_mock(side_effect=True)


async def test_entry_reloading(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test the entry is reloaded correctly when settings change."""
    reolink_connect.is_nvr = False
    reolink_connect.logout.reset_mock()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert reolink_connect.logout.call_count == 0
    assert config_entry.title == "test_reolink_name"

    hass.config_entries.async_update_entry(config_entry, title="New Name")
    await hass.async_block_till_done()

    assert reolink_connect.logout.call_count == 1
    assert config_entry.title == "New Name"

    reolink_connect.is_nvr = True


@pytest.mark.parametrize(
    ("attr", "value", "expected_models"),
    [
        (
            None,
            None,
            [TEST_HOST_MODEL, TEST_CAM_MODEL],
        ),
        (
            "is_nvr",
            False,
            [TEST_HOST_MODEL, TEST_CAM_MODEL],
        ),
        ("channels", [], [TEST_HOST_MODEL]),
        (
            "camera_online",
            Mock(return_value=False),
            [TEST_HOST_MODEL],
        ),
        (
            "channel_for_uid",
            Mock(return_value=-1),
            [TEST_HOST_MODEL],
        ),
    ],
)
async def test_removing_disconnected_cams(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    attr: str | None,
    value: Any,
    expected_models: list[str],
) -> None:
    """Test device and entity registry are cleaned up when camera is removed."""
    reolink_connect.channels = [0]
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    # setup CH 0 and NVR switch entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    device_models = [device.model for device in device_entries]
    assert sorted(device_models) == sorted([TEST_HOST_MODEL, TEST_CAM_MODEL])

    # Try to remove the device after 'disconnecting' a camera.
    if attr is not None:
        original = getattr(reolink_connect, attr)
        setattr(reolink_connect, attr, value)
    expected_success = TEST_CAM_MODEL not in expected_models
    for device in device_entries:
        if device.model == TEST_CAM_MODEL:
            response = await client.remove_device(device.id, config_entry.entry_id)
            assert response["success"] == expected_success

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    device_models = [device.model for device in device_entries]
    assert sorted(device_models) == sorted(expected_models)

    if attr is not None:
        setattr(reolink_connect, attr, original)


@pytest.mark.parametrize(
    ("attr", "value", "expected_models"),
    [
        (
            None,
            None,
            [TEST_HOST_MODEL, TEST_CAM_MODEL, CHIME_MODEL],
        ),
        (
            "connect_state",
            -1,
            [TEST_HOST_MODEL, TEST_CAM_MODEL],
        ),
        (
            "remove",
            -1,
            [TEST_HOST_MODEL, TEST_CAM_MODEL],
        ),
    ],
)
async def test_removing_chime(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    test_chime: Chime,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    attr: str | None,
    value: Any,
    expected_models: list[str],
) -> None:
    """Test removing a chime."""
    reolink_connect.channels = [0]
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    # setup CH 0 and NVR switch entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    device_models = [device.model for device in device_entries]
    assert sorted(device_models) == sorted(
        [TEST_HOST_MODEL, TEST_CAM_MODEL, CHIME_MODEL]
    )

    if attr == "remove":

        async def test_remove_chime(*args, **key_args):
            """Remove chime."""
            test_chime.connect_state = -1

        test_chime.remove = test_remove_chime
    elif attr is not None:
        setattr(test_chime, attr, value)

    # Try to remove the device after 'disconnecting' a chime.
    expected_success = CHIME_MODEL not in expected_models
    for device in device_entries:
        if device.model == CHIME_MODEL:
            response = await client.remove_device(device.id, config_entry.entry_id)
            assert response["success"] == expected_success

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    device_models = [device.model for device in device_entries]
    assert sorted(device_models) == sorted(expected_models)


@pytest.mark.parametrize(
    (
        "original_id",
        "new_id",
        "original_dev_id",
        "new_dev_id",
        "domain",
        "support_uid",
        "support_ch_uid",
    ),
    [
        (
            TEST_MAC,
            f"{TEST_MAC}_firmware",
            f"{TEST_MAC}",
            f"{TEST_MAC}",
            Platform.UPDATE,
            False,
            False,
        ),
        (
            TEST_MAC,
            f"{TEST_UID}_firmware",
            f"{TEST_MAC}",
            f"{TEST_UID}",
            Platform.UPDATE,
            True,
            False,
        ),
        (
            f"{TEST_MAC}_0_record_audio",
            f"{TEST_UID}_0_record_audio",
            f"{TEST_MAC}_ch0",
            f"{TEST_UID}_ch0",
            Platform.SWITCH,
            True,
            False,
        ),
        (
            f"{TEST_MAC}_chime123456789_play_ringtone",
            f"{TEST_UID}_chime123456789_play_ringtone",
            f"{TEST_MAC}_chime123456789",
            f"{TEST_UID}_chime123456789",
            Platform.SELECT,
            True,
            False,
        ),
        (
            f"{TEST_MAC}_0_record_audio",
            f"{TEST_MAC}_{TEST_UID_CAM}_record_audio",
            f"{TEST_MAC}_ch0",
            f"{TEST_MAC}_{TEST_UID_CAM}",
            Platform.SWITCH,
            False,
            True,
        ),
        (
            f"{TEST_MAC}_0_record_audio",
            f"{TEST_UID}_{TEST_UID_CAM}_record_audio",
            f"{TEST_MAC}_ch0",
            f"{TEST_UID}_{TEST_UID_CAM}",
            Platform.SWITCH,
            True,
            True,
        ),
        (
            f"{TEST_UID}_0_record_audio",
            f"{TEST_UID}_{TEST_UID_CAM}_record_audio",
            f"{TEST_UID}_ch0",
            f"{TEST_UID}_{TEST_UID_CAM}",
            Platform.SWITCH,
            True,
            True,
        ),
    ],
)
async def test_migrate_entity_ids(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    original_id: str,
    new_id: str,
    original_dev_id: str,
    new_dev_id: str,
    domain: Platform,
    support_uid: bool,
    support_ch_uid: bool,
) -> None:
    """Test entity ids that need to be migrated."""

    def mock_supported(ch, capability):
        if capability == "UID" and ch is None:
            return support_uid
        if capability == "UID":
            return support_ch_uid
        return True

    reolink_connect.channels = [0]
    reolink_connect.supported = mock_supported

    dev_entry = device_registry.async_get_or_create(
        identifiers={(DOMAIN, original_dev_id)},
        config_entry_id=config_entry.entry_id,
        disabled_by=None,
    )

    entity_registry.async_get_or_create(
        domain=domain,
        platform=DOMAIN,
        unique_id=original_id,
        config_entry=config_entry,
        suggested_object_id=original_id,
        disabled_by=None,
        device_id=dev_entry.id,
    )

    assert entity_registry.async_get_entity_id(domain, DOMAIN, original_id)
    assert entity_registry.async_get_entity_id(domain, DOMAIN, new_id) is None

    assert device_registry.async_get_device(identifiers={(DOMAIN, original_dev_id)})
    if new_dev_id != original_dev_id:
        assert (
            device_registry.async_get_device(identifiers={(DOMAIN, new_dev_id)}) is None
        )

    # setup CH 0 and host entities/device
    with patch("homeassistant.components.reolink.PLATFORMS", [domain]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id(domain, DOMAIN, original_id) is None
    assert entity_registry.async_get_entity_id(domain, DOMAIN, new_id)

    if new_dev_id != original_dev_id:
        assert (
            device_registry.async_get_device(identifiers={(DOMAIN, original_dev_id)})
            is None
        )
    assert device_registry.async_get_device(identifiers={(DOMAIN, new_dev_id)})


async def test_no_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry, issue_registry: ir.IssueRegistry
) -> None:
    """Test no repairs issue is raised when http local url is used."""
    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "http://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (DOMAIN, "https_webhook") not in issue_registry.issues
    assert (DOMAIN, "webhook_url") not in issue_registry.issues
    assert (DOMAIN, "enable_port") not in issue_registry.issues
    assert (DOMAIN, "firmware_update") not in issue_registry.issues
    assert (DOMAIN, "ssl") not in issue_registry.issues


async def test_https_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repairs issue is raised when https local url is used."""
    reolink_connect.get_states = test_wait
    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "https://test_homeassistant_address"}
    )

    with (
        patch("homeassistant.components.reolink.host.FIRST_ONVIF_TIMEOUT", new=0),
        patch(
            "homeassistant.components.reolink.host.FIRST_ONVIF_LONG_POLL_TIMEOUT", new=0
        ),
        patch(
            "homeassistant.components.reolink.host.ReolinkHost._async_long_polling",
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (DOMAIN, "https_webhook") in issue_registry.issues


async def test_ssl_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repairs issue is raised when global ssl certificate is used."""
    reolink_connect.get_states = test_wait
    assert await async_setup_component(hass, "webhook", {})
    hass.config.api.use_ssl = True

    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "http://test_homeassistant_address"}
    )

    with (
        patch("homeassistant.components.reolink.host.FIRST_ONVIF_TIMEOUT", new=0),
        patch(
            "homeassistant.components.reolink.host.FIRST_ONVIF_LONG_POLL_TIMEOUT", new=0
        ),
        patch(
            "homeassistant.components.reolink.host.ReolinkHost._async_long_polling",
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (DOMAIN, "ssl") in issue_registry.issues


@pytest.mark.parametrize("protocol", ["rtsp", "rtmp"])
async def test_port_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    protocol: str,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repairs issue is raised when auto enable of ports fails."""
    reolink_connect.set_net_port.side_effect = ReolinkError("Test error")
    reolink_connect.onvif_enabled = False
    reolink_connect.rtsp_enabled = False
    reolink_connect.rtmp_enabled = False
    reolink_connect.protocol = protocol
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (DOMAIN, "enable_port") in issue_registry.issues

    reolink_connect.set_net_port.reset_mock(side_effect=True)


async def test_webhook_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repairs issue is raised when the webhook url is unreachable."""
    reolink_connect.get_states = test_wait
    with (
        patch("homeassistant.components.reolink.host.FIRST_ONVIF_TIMEOUT", new=0),
        patch(
            "homeassistant.components.reolink.host.FIRST_ONVIF_LONG_POLL_TIMEOUT", new=0
        ),
        patch(
            "homeassistant.components.reolink.host.ReolinkHost._async_long_polling",
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (DOMAIN, "webhook_url") in issue_registry.issues


async def test_firmware_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test firmware issue is raised when too old firmware is used."""
    reolink_connect.camera_sw_version_update_required.return_value = True
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (DOMAIN, "firmware_update_host") in issue_registry.issues


async def test_new_device_discovered(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the entry is reloaded when a new camera or chime is detected."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    reolink_connect.logout.reset_mock()

    assert reolink_connect.logout.call_count == 0
    reolink_connect.new_devices = True

    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert reolink_connect.logout.call_count == 1


async def test_port_changed(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test config_entry port update when it has changed during initial login."""
    assert config_entry.data[CONF_PORT] == TEST_PORT
    reolink_connect.port = 4567

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.data[CONF_PORT] == 4567
