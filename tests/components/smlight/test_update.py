"""Tests for the SMLIGHT update platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysmlight import Firmware, Info
from pysmlight.const import Events as SmEvents
from pysmlight.sse import MessageEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import SCAN_FIRMWARE_INTERVAL
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as PLATFORM,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import get_mock_event_function
from .conftest import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
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
        ver="v2.3.6",
        mode="ESP",
        notes=None,
    )
]


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
    """Test setup of SMLIGHT switches."""
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    await hass.config_entries.async_unload(entry.entry_id)


async def test_update_firmware(
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
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.5.2"

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
    assert state.attributes[ATTR_IN_PROGRESS] == 50

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.FW_UPD_done)

    event_function(MOCK_FIRMWARE_DONE)

    mock_smlight_client.get_info.return_value = Info(
        sw_version="v2.5.2",
    )

    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.5.2"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.5.2"


async def test_update_legacy_firmware_v2(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test firmware update for legacy v2 firmware."""
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
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.5.2"

    await hass.services.async_call(
        PLATFORM,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=False,
    )

    assert len(mock_smlight_client.fw_update.mock_calls) == 1

    event_function = get_mock_event_function(mock_smlight_client, SmEvents.ESP_UPD_done)

    event_function(MOCK_FIRMWARE_DONE)

    mock_smlight_client.get_info.return_value = Info(
        sw_version="v2.5.2",
    )

    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v2.5.2"
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.5.2"


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
    assert state.attributes[ATTR_LATEST_VERSION] == "v2.5.2"

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


async def test_update_release_notes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test firmware release notes."""
    await setup_integration(hass, mock_config_entry)
    ws_client = await hass_ws_client(hass)
    await hass.async_block_till_done()
    entity_id = "update.mock_title_core_firmware"

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

    mock_smlight_client.get_firmware_version.side_effect = None
    mock_smlight_client.get_firmware_version.return_value = MOCK_FIRMWARE_NOTES

    freezer.tick(SCAN_FIRMWARE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            "id": 2,
            "type": "update/release_notes",
            "entity_id": entity_id,
        }
    )
    result = await ws_client.receive_json()
    await hass.async_block_till_done()
    assert result["result"] is None
