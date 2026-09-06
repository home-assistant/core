"""Test for calendar platform of the Cookidoo integration."""

from collections.abc import Generator
from dataclasses import asdict
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

from cookidoo_api import (
    CookidooAuthException,
    CookidooParseException,
    CookidooRequestException,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import AUTH_DATA

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def calendar_only() -> Generator[None]:
    """Enable only the calendar platform."""
    with patch(
        "homeassistant.components.cookidoo.PLATFORMS",
        [Platform.CALENDAR],
    ):
        yield


@pytest.mark.usefixtures("mock_cookidoo_client")
async def test_calendar(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of calendar platform."""

    with patch("homeassistant.components.cookidoo.PLATFORMS", [Platform.CALENDAR]):
        await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, cookidoo_config_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.usefixtures("mock_cookidoo_client")
async def test_get_events(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching events from Cookidoo calendar."""

    with patch("homeassistant.components.cookidoo.PLATFORMS", [Platform.CALENDAR]):
        await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    entities = er.async_entries_for_config_entry(
        entity_registry, cookidoo_config_entry.entry_id
    )
    assert len(entities) == 1
    entity_id = entities[0].entity_id

    resp = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": datetime(2025, 3, 4, tzinfo=UTC),
            "end_date_time": datetime(2025, 3, 6, tzinfo=UTC),
        },
        target={"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    assert resp == snapshot


@pytest.mark.parametrize(
    "login_exception",
    [
        pytest.param(CookidooAuthException(), id="auth"),
        pytest.param(CookidooRequestException(), id="request"),
        pytest.param(CookidooParseException(), id="parse"),
        pytest.param(None, id="retry_fails_after_successful_login"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_get_events_login_failure(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    login_exception: Exception | None,
) -> None:
    """Test calendar handles login failures gracefully during event fetch.

    With no login exception the login succeeds and the retried fetch fails
    instead, which must be reported the same way.
    """

    with patch("homeassistant.components.cookidoo.PLATFORMS", [Platform.CALENDAR]):
        await setup_integration(hass, cookidoo_config_entry)

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    entities = er.async_entries_for_config_entry(
        entity_registry, cookidoo_config_entry.entry_id
    )
    assert len(entities) == 1
    entity_id = entities[0].entity_id

    # First call to get_recipes_in_calendar_week raises auth, login also fails
    mock_cookidoo_client.get_recipes_in_calendar_week.side_effect = (
        CookidooAuthException()
    )
    mock_cookidoo_client.login.side_effect = login_exception

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "start_date_time": datetime(2025, 3, 4, tzinfo=UTC),
                "end_date_time": datetime(2025, 3, 6, tzinfo=UTC),
            },
            target={"entity_id": entity_id},
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_get_events_relogin_persists_tokens(
    hass: HomeAssistant,
    cookidoo_config_entry_with_token: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test tokens of a calendar re-login are persisted on the config entry."""
    await setup_integration(hass, cookidoo_config_entry_with_token)

    entities = er.async_entries_for_config_entry(
        entity_registry, cookidoo_config_entry_with_token.entry_id
    )
    entity_id = entities[0].entity_id

    week_plan = mock_cookidoo_client.get_recipes_in_calendar_week.return_value
    mock_cookidoo_client.get_recipes_in_calendar_week.side_effect = [
        CookidooAuthException(),
        week_plan,
        week_plan,
    ]
    mock_cookidoo_client.login.side_effect = lambda: setattr(
        mock_cookidoo_client, "auth_data", AUTH_DATA
    )

    await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": datetime(2025, 3, 4, tzinfo=UTC),
            "end_date_time": datetime(2025, 3, 6, tzinfo=UTC),
        },
        target={"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    assert cookidoo_config_entry_with_token.data[CONF_TOKEN] == asdict(AUTH_DATA)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_get_events_persists_rotated_tokens(
    hass: HomeAssistant,
    cookidoo_config_entry_with_token: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test tokens rotated during a plain calendar fetch are persisted."""
    await setup_integration(hass, cookidoo_config_entry_with_token)

    entities = er.async_entries_for_config_entry(
        entity_registry, cookidoo_config_entry_with_token.entry_id
    )
    entity_id = entities[0].entity_id

    # The library rotates the tokens while serving the fetch, without a login
    week_plan = mock_cookidoo_client.get_recipes_in_calendar_week.return_value

    def _rotate(week_day: date) -> list:
        mock_cookidoo_client.auth_data = AUTH_DATA
        return week_plan

    mock_cookidoo_client.get_recipes_in_calendar_week.side_effect = _rotate

    await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "start_date_time": datetime(2025, 3, 4, tzinfo=UTC),
            "end_date_time": datetime(2025, 3, 6, tzinfo=UTC),
        },
        target={"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    mock_cookidoo_client.login.assert_not_awaited()
    assert cookidoo_config_entry_with_token.data[CONF_TOKEN] == asdict(AUTH_DATA)
