"""Tests for Imou select platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import PARAM_CURRENT_OPTION, PARAM_OPTIONS
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imou.const import (
    PARAM_MODE,
    PARAM_NIGHT_VISION_MODE,
    PARAM_STATE,
    PARAM_STATUS,
)
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import DEFAULT_SELECTS, UNKNOWN_SELECT_KEY, create_online_device

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def _apply_select_option(
    device: ImouHaDevice, select_type: str, option: str
) -> None:
    """Simulate the vendor API updating select state after a command."""
    device.selects[select_type][PARAM_CURRENT_OPTION] = option


SELECT_MOCK_DEVICES = [
    create_online_device(
        "d1",
        "Device 1",
        button_keys=(),
        selects=DEFAULT_SELECTS,
    ),
]


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "d1",
                "Device 1",
                button_keys=(),
                selects={
                    UNKNOWN_SELECT_KEY: {
                        PARAM_CURRENT_OPTION: "0",
                        PARAM_OPTIONS: ["0", "1"],
                    },
                    PARAM_NIGHT_VISION_MODE: {
                        PARAM_CURRENT_OPTION: "0",
                        PARAM_OPTIONS: ["0", "1", "2", "3"],
                    },
                },
            )
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_setup_ignores_unknown_select_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Unknown select keys from the API are not turned into entities."""
    registry = er.async_get(hass)  # pylint: disable=home-assistant-tests-registry-fixtures
    entries = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    select_entries = [entry for entry in entries if entry.domain == SELECT_DOMAIN]
    assert len(select_entries) == 1
    assert select_entries[0].translation_key == PARAM_NIGHT_VISION_MODE
