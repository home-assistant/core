"""Test Volvo locks."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import VolvoApiException, VolvoCarsCommandResult

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import configure_mock
from .const import DEFAULT_VIN

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_api", "full_model")
@pytest.mark.parametrize(
    "full_model",
    ["ex30_2024", "s90_diesel_2018", "xc40_electric_2024", "xc90_petrol_2019"],
)
async def test_lock(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lock."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.LOCK]):
        assert await setup_integration()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("full_model")
@pytest.mark.parametrize(
    "action",
    [SERVICE_UNLOCK, SERVICE_LOCK],
)
async def test_unlock_lock(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
    action: str,
) -> None:
    """Test unlock/lock."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.LOCK]):
        assert await setup_integration()

    await hass.services.async_call(
        LOCK_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "lock.volvo_xc40_central_lock"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(mock_api.async_execute_command.mock_calls) == 1


@pytest.mark.usefixtures("full_model")
@pytest.mark.parametrize(
    "action",
    [SERVICE_UNLOCK, SERVICE_LOCK],
)
async def test_unlock_lock_error(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
    action: str,
) -> None:
    """Test unlock/lock with error response."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.LOCK]):
        assert await setup_integration()

    configure_mock(mock_api.async_execute_command, side_effect=VolvoApiException)

    entity_id = "lock.volvo_xc40_central_lock"
    assert hass.states.get(entity_id).state == LockState.LOCKED

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            action,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == LockState.LOCKED


@pytest.mark.usefixtures("full_model")
async def test_unlock_failure(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[bool]],
    mock_api: VolvoCarsApi,
) -> None:
    """Test unlock/lock with error response."""

    with patch("homeassistant.components.volvo.PLATFORMS", [Platform.LOCK]):
        assert await setup_integration()

    configure_mock(
        mock_api.async_execute_command,
        return_value=VolvoCarsCommandResult(
            vin=DEFAULT_VIN, invoke_status="CONNECTION_FAILURE", message=""
        ),
    )

    entity_id = "lock.volvo_xc40_central_lock"
    assert hass.states.get(entity_id).state == LockState.LOCKED

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == LockState.LOCKED
