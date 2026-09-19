"""Test the Remootio cover platform."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from pyremootio import RemootioActionError, RemootioTimeoutError
from pyremootio.models import ActionResponse, ActionType, DoorState, RemootioEvent
import pytest

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    CoverDeviceClass,
)
from homeassistant.components.remootio.const import DOMAIN, device_name
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_SERIAL, USER_INPUT

from tests.common import MockConfigEntry


def _entity_id(hass: HomeAssistant) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("cover", DOMAIN, MOCK_SERIAL)
    assert entity_id is not None
    return entity_id


async def test_cover_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the garage cover is created with a stable unique id."""
    entity_id = _entity_id(hass)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.GARAGE

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == MOCK_SERIAL


async def test_multiple_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test each config entry creates an independent cover and client."""
    second_serial = "2462abe6bda0nfmcfabb"
    clients = [AsyncMock(), AsyncMock()]
    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            unique_id=serial,
            data={**USER_INPUT, CONF_HOST: host},
            title=device_name(serial),
        )
        for serial, host in (
            (MOCK_SERIAL, USER_INPUT[CONF_HOST]),
            (second_serial, "192.168.1.51"),
        )
    ]

    for client in clients:
        client.remootio_version = "remootio-3"
        client.state = DoorState.CLOSED
        client.authenticated = True
        client.listen = MagicMock(return_value=MagicMock())
        client.listen_connection = MagicMock(return_value=MagicMock())
        client.listen_auth_failure = MagicMock(return_value=MagicMock())
        client.enable_reconnect = MagicMock()

    with patch("homeassistant.components.remootio.RemootioClient", side_effect=clients):
        for entry in entries:
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    first_entity_id = entity_registry.async_get_entity_id("cover", DOMAIN, MOCK_SERIAL)
    second_entity_id = entity_registry.async_get_entity_id(
        "cover", DOMAIN, second_serial
    )
    assert first_entity_id is not None
    assert second_entity_id is not None

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: first_entity_id},
        blocking=True,
    )
    clients[0].open.assert_awaited_once()
    clients[1].open.assert_not_awaited()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: second_entity_id},
        blocking=True,
    )
    clients[0].close.assert_not_awaited()
    clients[1].close.assert_awaited_once()


async def test_cover_open_close(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test open and close call the matching client methods."""
    entity_id = _entity_id(hass)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_remootio_client.open.assert_awaited_once()
    mock_remootio_client.trigger.assert_not_called()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_remootio_client.close.assert_awaited_once()


async def test_cover_open_close_without_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test open/close output mode still uses OPEN/CLOSE with no status sensor."""
    entity_id = _entity_id(hass)
    mock_remootio_client.state = DoorState.NO_SENSOR

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_remootio_client.open.assert_awaited_once()
    mock_remootio_client.trigger.assert_not_called()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_remootio_client.close.assert_awaited_once()
    mock_remootio_client.trigger.assert_not_called()


def _no_sensor_error(action: ActionType) -> RemootioActionError:
    return RemootioActionError(
        ActionResponse(
            type=action,
            id=1,
            success=False,
            state=DoorState.NO_SENSOR,
            t100ms=0,
            relay_triggered=False,
            error_code="ERR_NO_SENSOR",
        )
    )


async def test_cover_impulse_without_sensor_falls_back_to_trigger(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test impulse mode without a sensor: OPEN/CLOSE fail, then TRIGGER."""
    entity_id = _entity_id(hass)
    mock_remootio_client.open.side_effect = _no_sensor_error(ActionType.OPEN)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_remootio_client.open.assert_awaited_once()
    mock_remootio_client.trigger.assert_awaited_once()

    mock_remootio_client.trigger.reset_mock()
    mock_remootio_client.close.side_effect = _no_sensor_error(ActionType.CLOSE)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_remootio_client.close.assert_awaited_once()
    mock_remootio_client.trigger.assert_awaited_once()


async def test_cover_state_from_events(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test pushed events update the cover state."""
    entity_id = _entity_id(hass)
    on_event = mock_remootio_client.listen.call_args[0][0]

    mock_remootio_client.state = DoorState.OPEN
    on_event(RemootioEvent(type="StateChange", state=DoorState.OPEN, cnt=1, t100ms=0))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OPEN

    mock_remootio_client.state = DoorState.NO_SENSOR
    on_event(
        RemootioEvent(type="StateChange", state=DoorState.NO_SENSOR, cnt=2, t100ms=0)
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_cover_unavailable_on_disconnect(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the cover becomes unavailable when the websocket drops."""
    entity_id = _entity_id(hass)
    on_connection = mock_remootio_client.listen_connection.call_args[0][0]
    name = f"Remootio device ({MOCK_SERIAL})"

    with caplog.at_level(logging.INFO):
        mock_remootio_client.authenticated = False
        on_connection(False)
        on_connection(False)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
        assert caplog.text.count(f"Disconnected from {name}") == 1
        assert f"Reconnected to {name}" not in caplog.text

        mock_remootio_client.authenticated = True
        on_connection(True)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_CLOSED
        assert caplog.text.count(f"Reconnected to {name}") == 1


async def test_cover_action_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test a rejected action is raised as HomeAssistantError."""
    entity_id = _entity_id(hass)
    mock_remootio_client.open.side_effect = RemootioActionError(
        ActionResponse(
            type=ActionType.OPEN,
            id=1,
            success=False,
            state=DoorState.CLOSED,
            t100ms=0,
            relay_triggered=False,
            error_code="ERR_RELAY_BUSY",
        )
    )

    with pytest.raises(HomeAssistantError, match="ERR_RELAY_BUSY"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_cover_library_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remootio_client: AsyncMock,
) -> None:
    """Test a dropped or timed-out action is raised as HomeAssistantError."""
    entity_id = _entity_id(hass)
    mock_remootio_client.close.side_effect = RemootioTimeoutError(
        "Timed out waiting for CLOSE response"
    )

    with pytest.raises(HomeAssistantError, match="Timed out waiting for CLOSE"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
