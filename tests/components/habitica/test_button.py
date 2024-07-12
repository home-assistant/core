"""Tests for Habitica button platform."""

from collections.abc import Generator
from http import HTTPStatus
import re
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.habitica.const import DEFAULT_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import assert_mock_called_with, json_data

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def button_only() -> Generator[None]:
    """Enable only the button platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.BUTTON],
    ):
        yield


@pytest.mark.usefixtures("mock_habitica")
async def test_buttons(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test button entities."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "api_url"),
    [
        ("button.test_user_allocate_all_stat_points", "user/allocate-now"),
        ("button.test_user_buy_a_health_potion", "user/buy-health-potion"),
        ("button.test_user_revive_from_death", "user/revive"),
        ("button.test_user_start_my_day", "cron"),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    entity_id: str,
    api_url: str,
) -> None:
    """Test button press method."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(f"{DEFAULT_URL}/api/v3/{api_url}", json={"data": None})

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert_mock_called_with(mock_habitica, "post", f"{DEFAULT_URL}/api/v3/{api_url}")


@pytest.mark.parametrize(
    ("entity_id", "api_url"),
    [
        ("button.test_user_allocate_all_stat_points", "user/allocate-now"),
        ("button.test_user_buy_a_health_potion", "user/buy-health-potion"),
        ("button.test_user_revive_from_death", "user/revive"),
        ("button.test_user_start_my_day", "cron"),
    ],
    ids=["allocate-points", "health-potion", "revive", "run-cron"],
)
@pytest.mark.parametrize(
    ("status_code", "msg"),
    [
        (HTTPStatus.TOO_MANY_REQUESTS, "Currently rate limited"),
        (HTTPStatus.BAD_REQUEST, "Unable to connect to Habitica"),
        (HTTPStatus.UNAUTHORIZED, "Unable to carry out this action"),
    ],
)
async def test_button_press_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    entity_id: str,
    api_url: str,
    status_code: HTTPStatus,
    msg: str,
) -> None:
    """Test button press exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/{api_url}",
        status=status_code,
        json={"data": None},
    )

    with pytest.raises(ServiceValidationError, match=msg):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert_mock_called_with(mock_habitica, "post", f"{DEFAULT_URL}/api/v3/{api_url}")


async def test_button_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test buttons are unavailable if conditions are not met."""

    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user", json=json_data("user_buttons_unavailable")
    )
    aioclient_mock.get(re.compile(r".*"), json={"data": []})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
