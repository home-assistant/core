"""Tests for the Habitica switch platform."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import DEFAULT_URL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import mock_called_with

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def switch_only() -> Generator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("mock_habitica")
async def test_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch entities."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("service_call"),
    [
        SERVICE_TURN_ON,
        SERVICE_TURN_OFF,
        SERVICE_TOGGLE,
    ],
)
async def test_turn_on_off_toggle(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service_call: str,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test switch turn on/off, toggle method."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/sleep",
        json={"success": True, "data": False},
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service_call,
        {ATTR_ENTITY_ID: "switch.test_user_rest_in_the_inn"},
        blocking=True,
    )

    assert mock_called_with(mock_habitica, "post", f"{DEFAULT_URL}/api/v3/user/sleep")


@pytest.mark.parametrize(
    ("service_call"),
    [
        SERVICE_TURN_ON,
        SERVICE_TURN_OFF,
        SERVICE_TOGGLE,
    ],
)
@pytest.mark.parametrize(
    ("status_code", "exception"),
    [
        (HTTPStatus.TOO_MANY_REQUESTS, ServiceValidationError),
        (HTTPStatus.BAD_REQUEST, HomeAssistantError),
    ],
)
async def test_turn_on_off_toggle_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service_call: str,
    mock_habitica: AiohttpClientMocker,
    status_code: HTTPStatus,
    exception: Exception,
) -> None:
    """Test switch turn on/off, toggle method."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/sleep",
        status=status_code,
        json={"success": True, "data": False},
    )

    with pytest.raises(expected_exception=exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service_call,
            {ATTR_ENTITY_ID: "switch.test_user_rest_in_the_inn"},
            blocking=True,
        )

    assert mock_called_with(mock_habitica, "post", f"{DEFAULT_URL}/api/v3/user/sleep")
