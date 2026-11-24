"""Tests for AEMET OpenData repairs."""

import base64
from datetime import UTC, datetime, timedelta
import json
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.aemet.const import API_KEY_EXPIRATION_WARNING_DAYS, DOMAIN
from homeassistant.components.aemet.repairs import (
    async_create_fix_flow,
    async_schedule_api_key_expiration_issue,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .util import async_init_integration


def _create_api_key(expiration: datetime) -> str:
    """Create a fake API key JWT with an expiration claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(json.dumps({"exp": expiration.timestamp()}).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}.signature"


def _create_entry(hass: HomeAssistant, api_key: str) -> MockConfigEntry:
    """Create an AEMET config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="40.30403754--3.72935236",
        data={
            CONF_API_KEY: api_key,
            CONF_LATITUDE: 40.30403754,
            CONF_LONGITUDE: -3.72935236,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _issue_id(entry: MockConfigEntry) -> str:
    """Return the repair issue ID for an entry."""
    return f"api_key_expiring_{entry.entry_id}"


async def test_schedule_expiration_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the expiration issue is scheduled before the key expires."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-01-01 00:00:00+00:00")
    expiration = datetime(2026, 1, 20, tzinfo=UTC)
    entry = _create_entry(hass, _create_api_key(expiration))

    cancel = async_schedule_api_key_expiration_issue(hass, entry)

    assert cancel is not None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None

    warning_start = expiration - timedelta(days=API_KEY_EXPIRATION_WARNING_DAYS)
    freezer.move_to(warning_start)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue is not None
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "api_key_expiring"
    cancel()


async def test_schedule_expiration_issue_immediately(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the expiration issue is created immediately inside the warning window."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-01-15 00:00:00+00:00")
    entry = _create_entry(hass, _create_api_key(datetime(2026, 1, 20, tzinfo=UTC)))

    assert async_schedule_api_key_expiration_issue(hass, entry) is None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is not None


async def test_schedule_expiration_issue_without_expiration(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test no issue is scheduled when the API key has no expiration."""
    entry = _create_entry(hass, "not-a-jwt")

    assert async_schedule_api_key_expiration_issue(hass, entry) is None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_setup_schedules_and_unload_cancels_expiration_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup schedules the expiration issue and unload cancels it."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-01-01 00:00:00+00:00")
    entry = await async_init_integration(
        hass,
        data={
            CONF_API_KEY: _create_api_key(datetime(2026, 3, 1, tzinfo=UTC)),
        },
    )

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_schedule_expiration_issue_with_non_string_key(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test no issue is scheduled when the stored API key is not a string."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="40.30403754--3.72935236",
        data={
            CONF_API_KEY: 123,
            CONF_LATITUDE: 40.30403754,
            CONF_LONGITUDE: -3.72935236,
        },
    )
    entry.add_to_hass(hass)

    assert async_schedule_api_key_expiration_issue(hass, entry) is None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_repair_flow_replaces_api_key(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the repair flow replaces the API key."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-01-15 00:00:00+00:00")
    entry = _create_entry(hass, _create_api_key(datetime(2026, 1, 20, tzinfo=UTC)))
    async_schedule_api_key_expiration_issue(hass, entry)
    issue_id = _issue_id(entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    flow = await async_create_fix_flow(hass, issue_id, {"entry_id": entry.entry_id})
    flow.hass = hass
    flow.flow_id = "test"

    result = await flow.async_step_init({"issue_id": issue_id})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with (
        patch(
            "homeassistant.components.aemet.repairs.async_validate_api_key",
            AsyncMock(return_value=None),
        ),
        patch.object(
            hass.config_entries, "async_schedule_reload"
        ) as async_schedule_reload,
    ):
        result = await flow.async_step_init()
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await flow.async_step_init({CONF_API_KEY: "new-key"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_API_KEY] == "new-key"
    async_schedule_reload.assert_called_once_with(entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    "error", ["invalid_api_key", "cannot_connect", "town_not_found"]
)
async def test_repair_flow_error(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    error: str,
) -> None:
    """Test the repair flow keeps the issue on an API error."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-01-15 00:00:00+00:00")
    entry = _create_entry(hass, _create_api_key(datetime(2026, 1, 20, tzinfo=UTC)))
    async_schedule_api_key_expiration_issue(hass, entry)
    issue_id = _issue_id(entry)

    flow = await async_create_fix_flow(hass, issue_id, {"entry_id": entry.entry_id})
    flow.hass = hass
    flow.flow_id = "test"

    with patch(
        "homeassistant.components.aemet.repairs.async_validate_api_key",
        AsyncMock(return_value=error),
    ):
        result = await flow.async_step_init({CONF_API_KEY: "invalid"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data[CONF_API_KEY] != "invalid"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


@pytest.mark.parametrize(
    ("data", "exception"),
    [
        (None, ValueError),
        ({}, ValueError),
        ({"entry_id": None}, TypeError),
        ({"entry_id": 123}, TypeError),
    ],
)
async def test_create_fix_flow_invalid_data(
    hass: HomeAssistant,
    data: dict[str, Any] | None,
    exception: type[Exception],
) -> None:
    """Test invalid repair data raises an error."""
    with pytest.raises(exception):
        await async_create_fix_flow(hass, "api_key_expiring_test", data)
