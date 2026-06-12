"""Tests for the Yoto switch platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from yoto_api import YotoError

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import PLAYER_ID

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("setup_credentials")


async def _setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the integration with only the switch platform."""
    with patch("homeassistant.components.yoto.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)


@pytest.mark.usefixtures("mock_yoto_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every Yoto switch entity."""
    await _setup(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("device_family", ["mini", "v2"])
async def test_no_auto_brightness_without_light_sensor(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_family: str,
) -> None:
    """Models without an ambient light sensor get no auto-brightness switches."""
    player = mock_yoto_client.players[PLAYER_ID]
    player.device = replace(player.device, device_family=device_family)

    await _setup(hass, mock_config_entry)

    assert hass.states.get("switch.nursery_yoto_day_automatic_brightness") is None
    assert hass.states.get("switch.nursery_yoto_night_automatic_brightness") is None
    assert hass.states.get("switch.nursery_yoto_bluetooth") is not None


@pytest.mark.parametrize(
    ("entity_id", "service", "expected_fields"),
    [
        pytest.param(
            "switch.nursery_yoto_bluetooth",
            SERVICE_TURN_ON,
            {"bluetooth_enabled": True},
            id="bluetooth-on",
        ),
        pytest.param(
            "switch.nursery_yoto_bluetooth",
            SERVICE_TURN_OFF,
            {"bluetooth_enabled": False},
            id="bluetooth-off",
        ),
        pytest.param(
            "switch.nursery_yoto_bluetooth_headphones",
            SERVICE_TURN_ON,
            {"bt_headphones_enabled": True},
            id="bluetooth-headphones-on",
        ),
        pytest.param(
            "switch.nursery_yoto_limit_headphone_volume",
            SERVICE_TURN_ON,
            {"headphones_volume_limited": True},
            id="limit-headphone-volume-on",
        ),
        pytest.param(
            "switch.nursery_yoto_repeat_all",
            SERVICE_TURN_ON,
            {"repeat_all": True},
            id="repeat-all-on",
        ),
        pytest.param(
            "switch.nursery_yoto_day_system_sounds",
            SERVICE_TURN_ON,
            {"day_sounds_off": False},
            id="day-sounds-on",
        ),
        pytest.param(
            "switch.nursery_yoto_day_system_sounds",
            SERVICE_TURN_OFF,
            {"day_sounds_off": True},
            id="day-sounds-off",
        ),
        pytest.param(
            "switch.nursery_yoto_night_system_sounds",
            SERVICE_TURN_ON,
            {"night_sounds_off": False},
            id="night-sounds-on",
        ),
        pytest.param(
            "switch.nursery_yoto_pause_with_volume_down",
            SERVICE_TURN_ON,
            {"pause_volume_down": True},
            id="pause-volume-down-on",
        ),
        pytest.param(
            "switch.nursery_yoto_pause_with_power_button",
            SERVICE_TURN_ON,
            {"pause_power_button": True},
            id="pause-power-button-on",
        ),
        pytest.param(
            "switch.nursery_yoto_day_automatic_brightness",
            SERVICE_TURN_ON,
            {"day_display_brightness_auto": True},
            id="day-auto-brightness-on",
        ),
        # Day brightness is auto in the fixture, so switching auto off falls
        # back to full manual brightness.
        pytest.param(
            "switch.nursery_yoto_day_automatic_brightness",
            SERVICE_TURN_OFF,
            {"day_display_brightness": 100},
            id="day-auto-brightness-off",
        ),
        # Night brightness has a manual value in the fixture, which is kept.
        pytest.param(
            "switch.nursery_yoto_night_automatic_brightness",
            SERVICE_TURN_OFF,
            {"night_display_brightness": 40},
            id="night-auto-brightness-off",
        ),
    ],
)
async def test_switch_actions(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    service: str,
    expected_fields: dict[str, bool | int],
) -> None:
    """Switch actions write the matching player config fields."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_yoto_client.set_player_config.assert_awaited_once_with(
        PLAYER_ID, **expected_fields
    )
    mock_yoto_client.update_player_info.assert_awaited_once_with(PLAYER_ID)


async def test_switch_action_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed config write raises a Home Assistant error."""
    await _setup(hass, mock_config_entry)
    mock_yoto_client.set_player_config.side_effect = YotoError("MQTT timeout")

    with pytest.raises(
        HomeAssistantError, match="Failed to update Yoto player settings"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.nursery_yoto_bluetooth"},
            blocking=True,
        )
