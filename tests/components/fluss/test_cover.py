"""Tests for the Fluss+ cover platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from fluss_api import FlussApiClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.components.fluss.const import DOMAIN
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


def _status_side_effect(statuses: dict[str, dict[str, Any]]):
    """Return a side_effect that yields per-device status payloads."""

    async def _get_status(device_id: str) -> dict[str, Any]:
        return {
            "status": {
                "internetConnected": True,
                **statuses.get(device_id, {}),
            }
        }

    return _get_status


async def _setup_cover_only(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration with only the cover platform forwarded."""
    with patch("homeassistant.components.fluss.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, entry)


async def test_covers(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cover entity registration."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {
            DEVICE_ID_1: {"openCloseStatus": "Closed"},
            DEVICE_ID_2: {"openCloseStatus": "Open"},
        }
    )
    await _setup_cover_only(hass, mock_config_entry)
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
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": status_value}}
    )
    await _setup_cover_only(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID_1)
    assert state is not None
    assert state.state == expected_state


async def test_cover_unavailable_when_offline(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Covers become unavailable when the device reports no internet."""

    async def _status(device_id: str) -> dict[str, Any]:
        return {"status": {"internetConnected": False, "openCloseStatus": "Closed"}}

    mock_api_client.async_get_device_status.side_effect = _status
    await _setup_cover_only(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID_1).state == STATE_UNAVAILABLE


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
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    await _setup_cover_only(hass, mock_config_entry)

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
async def test_cover_press_schedules_delayed_status_refresh(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
    post_status: str,
    expected_state: str,
) -> None:
    """A press defers a single-device status fetch by 10s."""
    initial_status = "Open" if post_status == "Closed" else "Closed"
    initial_state = STATE_OPEN if initial_status == "Open" else STATE_CLOSED
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": initial_status}}
    )
    await _setup_cover_only(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID_1).state == initial_state

    mock_api_client.async_get_device_status.reset_mock()
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": post_status}}
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID_1},
        blocking=True,
    )

    assert mock_api_client.async_get_device_status.call_count == 0
    assert hass.states.get(ENTITY_ID_1).state == initial_state

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    mock_api_client.async_get_device_status.assert_called_once_with(DEVICE_ID_1)
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
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    await _setup_cover_only(hass, mock_config_entry)

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
    """A device with openCloseStatus is a cover; a device without is a button."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get("cover.device_1") is not None
    assert entity_registry.async_get("button.device_1") is None
    assert entity_registry.async_get("button.device_2") is not None
    assert entity_registry.async_get("cover.device_2") is None


async def test_orphan_button_removed_on_setup(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A pre-existing button registry entry is removed if its device is now a cover."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "button", DOMAIN, DEVICE_ID_1, config_entry=mock_config_entry
    )
    assert (
        entity_registry.async_get_entity_id("button", DOMAIN, DEVICE_ID_1) is not None
    )

    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get_entity_id("button", DOMAIN, DEVICE_ID_1) is None
    assert entity_registry.async_get("cover.device_1") is not None
