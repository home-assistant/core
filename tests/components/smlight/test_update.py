"""Tests for the SMLIGHT update platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pysmlight import Firmware, Info, Radio
from pysmlight.const import Events as SmEvents
from pysmlight.sse import MessageEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import DOMAIN, SCAN_FIRMWARE_INTERVAL
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as PLATFORM,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import get_mock_event_function
from .conftest import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)
from tests.typing import WebSocketGenerator

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
    entity_id = "update.mock_title_core_firmware"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.3.6"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.7.5"

    await hass.services.async_call(
        PLATFORM,
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


async def test_update_zigbee2_firmware(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test update of zigbee2 firmware where available."""
    mock_info = Info.from_dict(load_json_object_fixture("info-MR1.json", DOMAIN))
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = mock_info
    await setup_integration(hass, mock_config_entry)
    entity_id = "update.mock_title_zigbee_firmware_2"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "20240314"
    assert state.attributes[ATTR_LATEST_VERSION] == "20240716"

    await hass.services.async_call(
        PLATFORM,
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
        PLATFORM,
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
        PLATFORM,
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


@patch("homeassistant.components.smlight.const.LOGGER.warning")
async def test_update_reboot_timeout(
    mock_warning: MagicMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
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
        await hass.services.async_call(
            PLATFORM,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=False,
        )

        assert len(mock_smlight_client.fw_update.mock_calls) == 1

        event_function = get_mock_event_function(
            mock_smlight_client, SmEvents.FW_UPD_done
        )

        event_function(MOCK_FIRMWARE_DONE)

        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        mock_warning.assert_called_once()


@pytest.mark.parametrize(
    "entity_id",
    [
        "update.mock_title_core_firmware",
        "update.mock_title_zigbee_firmware",
        "update.mock_title_zigbee_firmware_2",
    ],
)
async def test_update_release_notes(
    hass: HomeAssistant,
    entity_id: str,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test firmware release notes."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info.from_dict(
        load_json_object_fixture("info-MR1.json", DOMAIN)
    )
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
