"""Tests for the Fluss+ cover platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from fluss_api import FlussApiClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.components.fluss.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID_1 = "cover.device_1"
DEVICE_ID_1 = "2a303030sdj1"
DEVICE_ID_2 = "ape93k9302j2"


async def test_covers(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cover entity registration."""

    async def _status(device_id: str) -> dict[str, Any]:
        """Return distinct openCloseStatus per device for snapshot diversity."""
        return {
            "status": {
                "internetConnected": True,
                "openCloseStatus": "Closed" if device_id == DEVICE_ID_1 else "Open",
            }
        }

    mock_api_client.async_get_device_status.side_effect = _status
    with patch("homeassistant.components.fluss.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("status_value", "expected_state"),
    [("Closed", STATE_CLOSED), ("Open", STATE_OPEN)],
)
async def test_cover_state(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    status_value: str,
    expected_state: str,
) -> None:
    """The API returns either "Open" or "Closed" — verify both map correctly."""
    mock_api_client.async_get_device_status.return_value = {
        "status": {"internetConnected": True, "openCloseStatus": status_value}
    }
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID_1)
    assert state is not None
    assert state.state == expected_state


async def test_cover_unavailable_when_offline(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Covers become unavailable when the device reports no internet."""
    mock_api_client.async_get_device_status.return_value = {
        "status": {"internetConnected": False, "openCloseStatus": "Closed"}
    }
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID_1).state == STATE_UNAVAILABLE


async def test_cover_unavailable_on_transient_status_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed per-device status fetch raises UpdateFailed and marks the cover unavailable."""
    mock_api_client.async_get_device_status.return_value = {
        "status": {"internetConnected": True, "openCloseStatus": "Closed"}
    }
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_1).state == STATE_CLOSED

    mock_api_client.async_get_device_status.side_effect = FlussApiClientError("boom")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID_1).state == STATE_UNAVAILABLE
    assert entity_registry.async_get(ENTITY_ID_1) is not None


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_OPEN_COVER, "async_open_device"),
        (SERVICE_CLOSE_COVER, "async_close_device"),
    ],
)
async def test_cover_commands(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Open and close hit the matching API method."""
    mock_api_client.async_get_device_status.return_value = {
        "status": {"internetConnected": True, "openCloseStatus": "Closed"}
    }
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID_1},
        blocking=True,
    )
    await hass.async_block_till_done()

    getattr(mock_api_client, method).assert_called_once_with(DEVICE_ID_1)


@pytest.mark.parametrize(
    ("service", "method", "post_status", "expected_state"),
    [
        (SERVICE_OPEN_COVER, "async_open_device", "Open", STATE_OPEN),
        (SERVICE_CLOSE_COVER, "async_close_device", "Closed", STATE_CLOSED),
    ],
)
async def test_cover_press_triggers_debounced_refresh(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
    post_status: str,
    expected_state: str,
) -> None:
    """A press requests a coordinator refresh, debounced by the cooldown."""
    initial_status = "Open" if post_status == "Closed" else "Closed"
    initial_state = STATE_OPEN if initial_status == "Open" else STATE_CLOSED
    mock_api_client.async_get_device_status.return_value = {
        "status": {"internetConnected": True, "openCloseStatus": initial_status}
    }
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_1).state == initial_state

    pre_press_call_count = mock_api_client.async_get_device_status.call_count
    mock_api_client.async_get_device_status.return_value = {
        "status": {"internetConnected": True, "openCloseStatus": post_status}
    }

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID_1},
        blocking=True,
    )

    # immediate=False on the debouncer means no refresh until the cooldown.
    assert mock_api_client.async_get_device_status.call_count == pre_press_call_count
    assert hass.states.get(ENTITY_ID_1).state == initial_state

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    mock_api_client.async_get_device_status.assert_any_call(DEVICE_ID_1)
    assert hass.states.get(ENTITY_ID_1).state == expected_state


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_OPEN_COVER, "async_open_device"),
        (SERVICE_CLOSE_COVER, "async_close_device"),
    ],
)
async def test_cover_command_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Library errors are translated to HomeAssistantError with a translation key."""
    mock_api_client.async_get_device_status.return_value = {
        "status": {"internetConnected": True, "openCloseStatus": "Closed"}
    }
    await setup_integration(hass, mock_config_entry)

    getattr(mock_api_client, method).side_effect = FlussApiClientError("boom")

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID_1},
            blocking=True,
        )
    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "command_failed"


async def test_mixed_device_dispatch(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device with openCloseStatus exposes both a cover and a button; a device without exposes only a button."""

    async def _status(device_id: str) -> dict[str, Any]:
        """Return openCloseStatus for device 1; omit it for device 2."""
        if device_id == DEVICE_ID_1:
            return {"status": {"internetConnected": True, "openCloseStatus": "Closed"}}
        return {"status": {"internetConnected": True}}

    mock_api_client.async_get_device_status.side_effect = _status
    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get("cover.device_1") is not None
    assert entity_registry.async_get("button.device_1") is not None
    assert entity_registry.async_get("button.device_2") is not None
    assert entity_registry.async_get("cover.device_2") is None
