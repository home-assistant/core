"""Tests for the Fluss+ cover platform."""

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

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID_1 = "cover.device_1"
ENTITY_ID_2 = "cover.device_2"
DEVICE_ID_1 = "2a303030sdj1"
DEVICE_ID_2 = "ape93k9302j2"


def _status_side_effect(
    statuses: dict[str, dict[str, Any]],
):
    """Return a side_effect that yields per-device status payloads.

    Devices not present in ``statuses`` get a default online payload with no
    ``openCloseStatus`` key so they continue to register as buttons.
    """

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
    """The API contract is exactly "Open" or "Closed" — verify both map correctly."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": status_value}}
    )
    await _setup_cover_only(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID_1)
    assert state is not None
    assert state.state == expected_state


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
    """Open and close call the matching API method and trigger a refresh."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    await _setup_cover_only(hass, mock_config_entry)
    mock_api_client.async_get_device_status.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID_1},
        blocking=True,
    )
    await hass.async_block_till_done()

    getattr(mock_api_client, method).assert_called_once_with(DEVICE_ID_1)
    assert mock_api_client.async_get_device_status.call_count >= 1


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
    """Library errors are translated to HomeAssistantError."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    await _setup_cover_only(hass, mock_config_entry)

    getattr(mock_api_client, method).side_effect = FlussApiClientError("boom")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID_1},
            blocking=True,
        )


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


async def test_cover_promotes_button_when_capability_appears(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device that initially fails its status fetch registers as a button.

    On a later refresh that exposes ``openCloseStatus``, the button entity is
    removed from the registry and a cover entity replaces it.
    """
    mock_api_client.async_get_device_status.side_effect = FlussApiClientError("flaky")
    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get("button.device_1") is not None
    assert entity_registry.async_get("cover.device_1") is None

    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert entity_registry.async_get("cover.device_1") is not None
    assert entity_registry.async_get("button.device_1") is None


async def test_cover_state_preserved_on_transient_status_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed per-device status call must not drop is_closed to None."""
    mock_api_client.async_get_device_status.side_effect = _status_side_effect(
        {DEVICE_ID_1: {"openCloseStatus": "Closed"}}
    )
    await _setup_cover_only(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data[DEVICE_ID_1].is_closed is True

    mock_api_client.async_get_device_status.side_effect = FlussApiClientError("flaky")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    device = coordinator.data[DEVICE_ID_1]
    assert device.is_closed is True
    assert device.has_position_sensor is True
    assert device.internet_connected is False
    assert hass.states.get(ENTITY_ID_1).state == STATE_UNAVAILABLE
