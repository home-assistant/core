"""Tests for the WLED button platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wled import WLEDConnectionError, WLEDError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.wled.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
    pytest.mark.freeze_time("2021-11-04 17:36:59+01:00"),
]


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.wled.PLATFORMS", [Platform.BUTTON]):
        yield


async def test_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_snapshot(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device snapshot."""
    assert (entity_entry := entity_registry.async_get("button.wled_rgb_light_restart"))

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


async def test_button_restart(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_wled: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the behavior of the restart button."""
    assert (state := hass.states.get("button.wled_rgb_light_restart"))

    assert state.state == STATE_UNKNOWN
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
        blocking=True,
    )
    assert mock_wled.reset.call_count == 1
    mock_wled.reset.assert_called_with()

    assert (state := hass.states.get("button.wled_rgb_light_restart"))
    assert state.state == "2021-11-04T16:37:00+00:00"


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_translation_key"),
    [
        (WLEDError, "2021-11-04T16:37:00+00:00", "invalid_response_wled_error"),
        (WLEDConnectionError, STATE_UNAVAILABLE, "connection_error"),
    ],
)
async def test_button_restart_errors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_wled: MagicMock,
    side_effect: Exception,
    expected_state: str,
    expected_translation_key: str,
) -> None:
    """Test the error handling of the restart button."""
    # Test with WLED connection error
    mock_wled.reset.side_effect = side_effect
    with pytest.raises(HomeAssistantError) as ex:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wled_rgb_light_restart"},
            blocking=True,
        )

    assert ex.value.translation_domain == DOMAIN
    assert ex.value.translation_key == expected_translation_key

    # Ensure this made the entity unavailable
    assert (state := hass.states.get("button.wled_rgb_light_restart"))
    assert state.state == expected_state


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_button_next_playlist_entry(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the next playlist entry button skips to the next entry."""
    mock_wled.update.return_value.state.playlist_id = 1

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.wled_websocket_next_playlist_entry"},
        blocking=True,
    )

    mock_wled.next_playlist_entry.assert_called_once_with()


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_button_next_playlist_entry_without_playlist(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the next playlist entry button tells there is no playlist running."""
    with pytest.raises(ServiceValidationError) as ex:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wled_websocket_next_playlist_entry"},
            blocking=True,
        )

    assert ex.value.translation_key == "no_playlist_running"
    mock_wled.next_playlist_entry.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_translation_key"),
    [
        (WLEDError, "2021-11-04T16:37:00+00:00", "invalid_response_wled_error"),
        (WLEDConnectionError, STATE_UNAVAILABLE, "connection_error"),
    ],
)
@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_button_next_playlist_entry_errors(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    side_effect: Exception,
    expected_state: str,
    expected_translation_key: str,
) -> None:
    """Test the error handling of the next playlist entry button."""
    mock_wled.update.return_value.state.playlist_id = 1
    mock_wled.next_playlist_entry.side_effect = side_effect
    with pytest.raises(HomeAssistantError) as ex:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.wled_websocket_next_playlist_entry"},
            blocking=True,
        )

    assert ex.value.translation_key == expected_translation_key
    assert (state := hass.states.get("button.wled_websocket_next_playlist_entry"))
    assert state.state == expected_state


async def test_button_next_playlist_entry_after_firmware_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the next playlist entry button follows the firmware's support."""
    # WLED 0.14 can't skip a playlist entry.
    assert not hass.states.get("button.wled_rgb_light_next_playlist_entry")

    data = await async_load_json_object_fixture(hass, "rgb.json", DOMAIN)
    data["info"]["ver"] = "0.15.0"
    mock_wled.update.return_value.update_from_dict(data)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("button.wled_rgb_light_next_playlist_entry")

    # Later updates don't add it a second time.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "does not generate unique IDs" not in caplog.text

    # Going back to firmware without it makes the button unavailable.
    data["info"]["ver"] = "0.14.4"
    mock_wled.update.return_value.update_from_dict(data)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("button.wled_rgb_light_next_playlist_entry"))
    assert state.state == STATE_UNAVAILABLE
