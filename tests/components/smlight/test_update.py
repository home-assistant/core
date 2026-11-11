"""Tests for the SMLIGHT update platform."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from pysmlight import Firmware, Info, Radio
from pysmlight.const import Events as SmEvents
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
from pysmlight.sse import MessageEvent
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import DOMAIN, SCAN_FIRMWARE_INTERVAL
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_UPDATE_PERCENTAGE,
    ATTR_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import entity_registry as er

from . import get_mock_event_function
from .conftest import setup_integration

pytestmark = [
    pytest.mark.usefixtures(
        "mock_smlight_client",
    )
]

MOCK_FIRMWARE_DONE = MessageEvent(
    type="FW_UPD_done",
    message="FW_UPD_done",
    data="",
    origin="http://slzb-06p10.local",
    last_event_id="",
)

MOCK_FIRMWARE_PROGRESS = MessageEvent(
    type="ZB_FW_prgs",
    message="ZB_FW_prgs",
    data="50",
    origin="http://slzb-06p10.local",
    last_event_id="",
)

MOCK_FIRMWARE_FAIL = MessageEvent(
    type="ZB_FW_err",
    message="ZB_FW_err",
    data="",
    origin="http://slzb-06p10.local",
    last_event_id="",
)

MOCK_FIRMWARE_NOTES = [
    Firmware(
        ver="v2.7.2",
        mode="ESP",
        notes=None,
    )
]

MOCK_RADIO = Radio(chip_index=1, zb_channel=0, zb_type=0, zb_version="20240716")


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.UPDATE]


async def test_update_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of SMLIGHT update entities."""
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.SENSOR, Platform.UPDATE]])
@pytest.mark.parametrize("error", [TimeoutError, ValueError])
@pytest.mark.parametrize(
    "entity_id",
    ["update.mock_title_core_firmware", "update.mock_title_zigbee_firmware"],
)
async def test_firmware_catalog_failure_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    error: type[Exception],
    entity_id: str,
) -> None:
    """Test background catalog failure and recovery without an initial candidate."""
    get_firmware = mock_smlight_client.get_firmware_version.side_effect
    mock_smlight_client.get_firmware_version.side_effect = error

    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("sensor.mock_title_core_chip_temp").state != STATE_UNAVAILABLE
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_smlight_client.get_firmware_version.side_effect = None
    mock_smlight_client.get_firmware_version.return_value = []
    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    mock_smlight_client.get_firmware_version.side_effect = error
    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_smlight_client.get_firmware_version.side_effect = get_firmware
    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_ON


async def test_installed_version_updates_without_firmware_catalog(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test local version changes are published while the catalog remains empty."""
    mock_smlight_client.get_firmware_version.side_effect = None
    mock_smlight_client.get_firmware_version.return_value = []

    await setup_integration(hass, mock_config_entry)

    entity_id = "update.mock_title_core_firmware"
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.3.6"
    assert state.attributes[ATTR_LATEST_VERSION] is None

    info = Info.from_dict(
        await async_load_json_object_fixture(hass, "info.json", DOMAIN)
    )
    info.sw_version = "v2.7.5"
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = info

    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.7.5"
    assert state.attributes[ATTR_LATEST_VERSION] is None


@pytest.mark.parametrize(
    ("catalog_responses", "expected_core_state"),
    [
        pytest.param(
            [SmlightConnectionError("Catalog unavailable")],
            STATE_UNKNOWN,
            id="core",
        ),
        pytest.param(
            [
                [Firmware(ver="v2.7.5", mode="ESP")],
                SmlightConnectionError("Catalog unavailable"),
            ],
            STATE_ON,
            id="radio",
        ),
    ],
)
async def test_catalog_connection_error_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    catalog_responses: list[list[Firmware] | SmlightConnectionError],
    expected_core_state: str,
) -> None:
    """Test catalog connection errors preserve availability and recover."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("update.mock_title_core_firmware").state == STATE_ON
    assert hass.states.get("update.mock_title_zigbee_firmware").state == STATE_ON

    side_effect = mock_smlight_client.get_firmware_version.side_effect
    mock_smlight_client.get_firmware_version.side_effect = catalog_responses

    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("update.mock_title_core_firmware").state == expected_core_state
    )
    assert hass.states.get("update.mock_title_zigbee_firmware").state == STATE_UNKNOWN

    mock_smlight_client.get_firmware_version.side_effect = side_effect
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-06p7",
        fw_channel="dev",
        sw_version="v2.7.5",
        radios=[Radio(chip_index=0, zb_type=0, zb_version="20250201")],
    )

    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("update.mock_title_core_firmware").state == STATE_OFF
    assert hass.states.get("update.mock_title_zigbee_firmware").state == STATE_OFF


@pytest.mark.parametrize(
    ("radios", "radio_type", "radio_idx", "latest_version"),
    [
        pytest.param(
            [
                Radio(zb_type=-1, chip_index=0),
                Radio(zb_type=1, chip_index=1, zb_version="20240314"),
                Radio(zb_type=5, chip_index=2, zb_version="20240716"),
            ],
            1,
            1,
            "20240716",
            id="unsupported_first",
        ),
        pytest.param(
            [
                Radio(zb_type=0, chip_index=0, zb_version="20240314"),
                Radio(zb_type=-1, chip_index=1),
                Radio(zb_type=5, chip_index=2, zb_version="20240716"),
            ],
            0,
            0,
            "20250201",
            id="unsupported_middle",
        ),
    ],
)
async def test_unsupported_radio_catalog(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    radios: list[Radio],
    radio_type: int,
    radio_idx: int,
    latest_version: str,
) -> None:
    """Test unsupported slots are skipped without shifting supported catalogs."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-Ultima3",
        addons={"zwave": True},
        fw_channel="dev",
        sw_version="v2.3.6",
        radios=radios,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_smlight_client.get_firmware_version.await_args_list == [
        call("dev", device="SLZB-Ultima3"),
        call(
            "dev",
            device="SLZB-Ultima3",
            mode="zigbee",
            zb_type=radio_type,
            idx=radio_idx,
        ),
        call("dev", device="SLZB-Ultima3", mode="zigbee", zb_type=5, idx=2),
    ]
    assert set(hass.states.async_entity_ids(UPDATE_DOMAIN)) == {
        "update.mock_title_core_firmware",
        "update.mock_title_zigbee_firmware",
        "update.mock_title_z_wave_firmware",
    }
    state = hass.states.get("update.mock_title_zigbee_firmware")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "20240314"
    assert state.attributes[ATTR_LATEST_VERSION] == latest_version

    state = hass.states.get("update.mock_title_z_wave_firmware")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "20240716"
    assert state.attributes[ATTR_LATEST_VERSION] == "20240716"


@patch("homeassistant.components.smlight.update.asyncio.sleep", return_value=None)
async def test_update_firmware(
    mock_sleep: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test firmware updates."""
    await setup_integration(hass, mock_config_entry)
    mock_smlight_client.get_firmware_version.reset_mock()
    entity_id = "update.mock_title_core_firmware"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.3.6"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.7.5"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=False,
    )

    assert len(mock_smlight_client.fw_update.mock_calls) == 1

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.ZB_FW_prgs)

    event_function(MOCK_FIRMWARE_PROGRESS)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 50

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.FW_UPD_done)

    event_function(MOCK_FIRMWARE_DONE)

    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        sw_version="v2.7.5",
    )

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.7.5"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.7.5"
    mock_smlight_client.get_firmware_version.assert_not_called()


async def test_update_zigbee2_firmware(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test update of zigbee2 firmware where available."""
    mock_info = Info.from_dict(
        await async_load_json_object_fixture(hass, "info-MR1.json", DOMAIN)
    )
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = mock_info
    await setup_integration(hass, mock_config_entry)
    entity_id = "update.mock_title_zigbee_firmware_2"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "20240314"
    assert state.attributes[ATTR_LATEST_VERSION] == "20240716"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=False,
    )

    assert len(mock_smlight_client.fw_update.mock_calls) == 1

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.FW_UPD_done)

    event_function(MOCK_FIRMWARE_DONE)

    mock_info.radios[1] = MOCK_RADIO

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "20240716"
    assert state.attributes[ATTR_LATEST_VERSION] == "20240716"


async def test_update_legacy_firmware_v2(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test firmware update for legacy v2 firmware."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        sw_version="v2.0.18",
        legacy_api=1,
        MAC="AA:BB:CC:DD:EE:FF",
    )
    await setup_integration(hass, mock_config_entry)
    entity_id = "update.mock_title_core_firmware"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.0.18"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.7.5"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=False,
    )

    assert len(mock_smlight_client.fw_update.mock_calls) == 1

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.ESP_UPD_done)

    event_function(MOCK_FIRMWARE_DONE)

    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        sw_version="v2.7.5",
    )

    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.7.5"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.7.5"


async def test_update_firmware_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test firmware updates."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "update.mock_title_core_firmware"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.3.6"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.7.5"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=False,
    )

    assert len(mock_smlight_client.fw_update.mock_calls) == 1

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.ZB_FW_err)

    async def _call_event_function(event: MessageEvent):
        event_function(event)

    with pytest.raises(HomeAssistantError):
        await _call_event_function(MOCK_FIRMWARE_FAIL)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None


@pytest.mark.parametrize(
    ("side_effect", "expected_exception", "expected_match", "expected_reauth"),
    [
        pytest.param(
            SmlightConnectionError,
            HomeAssistantError,
            "An error occurred while connecting to the SMLIGHT device",
            False,
            id="connection_error",
        ),
        pytest.param(
            SmlightAuthError,
            ConfigEntryAuthFailed,
            "Invalid authentication",
            True,
            id="auth_error",
        ),
    ],
)
async def test_update_install_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    side_effect: type[Exception],
    expected_exception: type[Exception],
    expected_match: str,
    expected_reauth: bool,
) -> None:
    """Test install service handles connection and auth errors from fw_update."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "update.mock_title_core_firmware"
    mock_smlight_client.fw_update.side_effect = side_effect

    with pytest.raises(expected_exception, match=expected_match):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert mock_config_entry.runtime_data.firmware.in_progress is False
    # All 3 SSE callbacks (progress, finished, failed) are unregistered on cleanup
    assert mock_smlight_client.sse.register_callback.return_value.call_count == 3

    reauth_flows = hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": SOURCE_REAUTH}
    )
    assert bool(reauth_flows) is expected_reauth


async def test_update_reboot_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test reboot timeout raises a translated user-facing error."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "update.mock_title_core_firmware"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.3.6"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.7.5"

    with (
        patch(
            "homeassistant.components.smlight.update.asyncio.timeout",
            side_effect=TimeoutError,
        ),
        patch(
            "homeassistant.components.smlight.update.asyncio.sleep",
            return_value=None,
        ),
    ):
        install_task = hass.async_create_task(
            hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
        )
        await asyncio.sleep(0)

        assert len(mock_smlight_client.fw_update.mock_calls) == 1

        event_function = get_mock_event_function(
            mock_smlight_client, SmEvents.FW_UPD_done
        )
        event_function(MOCK_FIRMWARE_DONE)

        with pytest.raises(
            HomeAssistantError,
            match=r"Timeout waiting for .* to reboot after update",
        ):
            await install_task

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None


@pytest.mark.parametrize(
    "entity_id",
    [
        "update.mock_title_core_firmware",
        "update.mock_title_zigbee_firmware",
        "update.mock_title_zigbee_firmware_2",
        "update.mock_title_z_wave_firmware",
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_ultima_client")
async def test_update_release_notes(
    hass: HomeAssistant,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test firmware release notes."""
    await setup_integration(hass, mock_config_entry)
    ws_client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": entity_id,
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] is not None


async def test_update_blank_release_notes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test firmware missing release notes."""

    entity_id = "update.mock_title_core_firmware"
    mock_smlight_client.get_firmware_version.side_effect = None
    mock_smlight_client.get_firmware_version.return_value = MOCK_FIRMWARE_NOTES

    await setup_integration(hass, mock_config_entry)
    ws_client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": entity_id,
        }
    )
    result = await ws_client.receive_json()
    await hass.async_block_till_done()
    assert result["result"] is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_ultima_client")
async def test_zwave_update_naming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Z-Wave radio (index 2) update entity naming."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("update.mock_title_z_wave_firmware")
    assert state is not None
    assert state.name == "Mock Title Z-Wave firmware"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zwave_update_naming_mr10(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test Z-Wave radio (index 1) update entity naming for MR10/MRW10."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-MRW10",
        u_device=True,
        radios=[
            Radio(zb_type=0, chip_index=0),
            Radio(zb_type=5, chip_index=1),
        ],
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("update.mock_title_z_wave_firmware")
    assert state is not None
    assert state.name == "Mock Title Z-Wave firmware"


@pytest.mark.parametrize(
    ("entity_id", "version", "installed_version", "latest_version", "updated_info"),
    [
        pytest.param(
            "update.mock_title_core_firmware",
            "0.9.9",
            "v2.3.6",
            "v2.7.5",
            Info(sw_version="0.9.9"),
            id="core",
        ),
        pytest.param(
            "update.mock_title_zigbee_firmware",
            "20240315",
            "20240314",
            "20250201",
            Info(radios=[Radio(chip_index=0, zb_type=0, zb_version="20240315")]),
            id="zigbee",
        ),
    ],
)
@patch("homeassistant.components.smlight.update.asyncio.sleep", return_value=None)
async def test_update_firmware_specific_version(
    mock_sleep: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    entity_id: str,
    version: str,
    installed_version: str,
    latest_version: str,
    updated_info: Info,
) -> None:
    """Test installing a specific firmware version, older than the latest."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_INSTALLED_VERSION] == installed_version
    assert state.attributes[ATTR_LATEST_VERSION] == latest_version

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id, ATTR_VERSION: version},
        blocking=False,
    )

    assert len(mock_smlight_client.fw_update.mock_calls) == 1
    firmware, idx = mock_smlight_client.fw_update.call_args.args
    assert firmware.ver == version
    assert idx == 0

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.FW_UPD_done)
    event_function(MOCK_FIRMWARE_DONE)

    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = updated_info
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_INSTALLED_VERSION] == version
    assert state.attributes[ATTR_LATEST_VERSION] == latest_version


@pytest.mark.parametrize(
    ("version", "translation_key"),
    [
        pytest.param("v9.9.9", "firmware_version_not_found", id="not_in_catalog"),
        pytest.param("", "firmware_version_not_found", id="empty"),
        pytest.param(
            "v2.3.6", "firmware_version_already_installed", id="already_installed"
        ),
    ],
)
async def test_update_firmware_specific_version_invalid(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    version: str,
    translation_key: str,
) -> None:
    """Test a version that cannot be installed is refused before flashing."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.mock_title_core_firmware", ATTR_VERSION: version},
            blocking=True,
        )

    mock_smlight_client.fw_update.assert_not_called()
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
