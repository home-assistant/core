"""Tests for the Yoto switch platform."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from yoto_api import YotoError

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
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


async def test_available_when_offline(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Config is written over REST, so entities stay available when offline."""
    player = next(iter(mock_yoto_client.players.values()))
    player.is_online = False

    await _setup(hass, mock_config_entry)

    state = hass.states.get("switch.nursery_yoto_bluetooth_pairing")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_auto_brightness_requires_light_sensor(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Auto-brightness switches only exist on devices with a light sensor."""
    player = next(iter(mock_yoto_client.players.values()))
    player.device = replace(player.device, device_family="v2")

    await _setup(hass, mock_config_entry)

    assert hass.states.get("switch.nursery_yoto_bluetooth_pairing") is not None
    assert hass.states.get("switch.nursery_yoto_day_mode_automatic_brightness") is None
    assert (
        hass.states.get("switch.nursery_yoto_night_mode_automatic_brightness") is None
    )


@pytest.mark.parametrize(
    ("entity_id", "expected_fields"),
    [
        pytest.param(
            "switch.nursery_yoto_bluetooth_pairing",
            {"bluetooth_enabled": True},
            id="bluetooth-pairing",
        ),
        pytest.param(
            "switch.nursery_yoto_maximum_headphone_volume",
            {"headphones_volume_limited": True},
            id="max-headphone-volume",
        ),
        pytest.param(
            "switch.nursery_yoto_day_mode_automatic_brightness",
            {"day_display_brightness_auto": True},
            id="day-auto-brightness",
        ),
        pytest.param(
            "switch.nursery_yoto_night_mode_automatic_brightness",
            {"night_display_brightness_auto": True},
            id="night-auto-brightness",
        ),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_fields: dict[str, bool],
) -> None:
    """Turning a switch on writes the matching player config field."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_yoto_client.set_player_config.assert_awaited_once_with(
        PLAYER_ID, **expected_fields
    )
    mock_yoto_client.update_player_info.assert_awaited_once_with(PLAYER_ID)


@pytest.mark.parametrize(
    ("entity_id", "expected_fields"),
    [
        pytest.param(
            "switch.nursery_yoto_bluetooth_pairing",
            {"bluetooth_enabled": False},
            id="bluetooth-pairing",
        ),
        pytest.param(
            "switch.nursery_yoto_maximum_headphone_volume",
            {"headphones_volume_limited": False},
            id="max-headphone-volume",
        ),
        pytest.param(
            "switch.nursery_yoto_day_mode_automatic_brightness",
            {"day_display_brightness_auto": False},
            id="day-auto-brightness",
        ),
        pytest.param(
            "switch.nursery_yoto_night_mode_automatic_brightness",
            {"night_display_brightness_auto": False},
            id="night-auto-brightness",
        ),
    ],
)
async def test_turn_off(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_fields: dict[str, bool],
) -> None:
    """Turning a switch off writes the matching player config field."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_yoto_client.set_player_config.assert_awaited_once_with(
        PLAYER_ID, **expected_fields
    )
    mock_yoto_client.update_player_info.assert_awaited_once_with(PLAYER_ID)


async def test_turn_on_failure(
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
            {ATTR_ENTITY_ID: "switch.nursery_yoto_bluetooth_pairing"},
            blocking=True,
        )
