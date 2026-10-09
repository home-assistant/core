"""Tests for the EnergyID directives coordinator."""

from collections.abc import Awaitable, Callable
import datetime as dt
from functools import partial
from typing import Any, NoReturn
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, ClientResponseError
from energyid_webhooks.directives import (
    DirectiveData,
    DirectiveResource,
    DirectiveSignal,
    SignalProvider,
)
import pytest

from homeassistant.components.energyid.const import CONF_ENABLE_DIRECTIVES, DOMAIN
from homeassistant.components.energyid.coordinator import EnergyIDDirectiveCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

DIRECTIVE_ID = "11111111-1111-1111-1111-111111111111"


def _directive_fixture(
    good_slots: int = 1,
) -> tuple[DirectiveResource, DirectiveData]:
    """Return a directive with 15 minute slots: good ones first, then a neutral one."""
    slot_start = dt_util.utcnow().replace(second=0, microsecond=0) - dt.timedelta(
        minutes=5
    )
    resource = DirectiveResource(
        id=DIRECTIVE_ID,
        title="Community planner",
        description="Community balance forecast",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="community",
            display_name="Energy community",
            logo_url=None,
        ),
    )
    points = [
        DirectiveSignal(
            timestamp=slot_start + dt.timedelta(minutes=15 * slot),
            signal="++",
            color="#00750e",
            raw_value=0,
        )
        for slot in range(good_slots)
    ]
    points.append(
        DirectiveSignal(
            timestamp=slot_start + dt.timedelta(minutes=15 * good_slots),
            signal="0",
            color="#EBEBEB",
            raw_value=0,
        )
    )
    schedule = DirectiveData(
        title=resource.title,
        description=resource.description,
        interval="PT15M",
        data=tuple(points),
    )
    return resource, schedule


async def _setup_with_directives(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> EnergyIDDirectiveCoordinator:
    """Set up the entry with directives enabled and return its coordinator."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry.runtime_data.directive_coordinator


async def test_directives_require_opt_in(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test EnergyID is not asked for directives until the user opts in."""
    mock_webhook_client.api_access_token = "device-token"

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.directive_coordinator
    assert coordinator.data.resources == {}
    mock_webhook_client.get_directives.assert_not_awaited()


async def test_current_and_next_signal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the coordinator derives the current signal and the next change."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    snapshot = coordinator.data.schedules[DIRECTIVE_ID]
    assert snapshot.schedule is schedule
    assert snapshot.current == schedule.data[0]
    assert snapshot.next_change == schedule.data[1]


@pytest.mark.parametrize(
    ("first_slot_offset", "expected_next"),
    [
        pytest.param(dt.timedelta(minutes=10), 0, id="future-only"),
        pytest.param(dt.timedelta(hours=-3), None, id="expired"),
    ],
)
async def test_schedule_without_current_signal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    first_slot_offset: dt.timedelta,
    expected_next: int | None,
) -> None:
    """Test a schedule that does not cover now has no current signal."""
    resource, schedule = _directive_fixture()
    point = DirectiveSignal(
        timestamp=dt_util.utcnow() + first_slot_offset,
        signal="++",
        color="#00750e",
        raw_value=0,
    )
    shifted = DirectiveData(
        title=schedule.title,
        description=schedule.description,
        interval=schedule.interval,
        data=(point,),
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=shifted)

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    snapshot = coordinator.data.schedules[DIRECTIVE_ID]
    assert snapshot.current is None
    assert snapshot.next_change == (None if expected_next is None else point)


async def test_failing_schedule_keeps_directive_granted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a directive whose schedule fails stays granted without a schedule."""
    resource, _ = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(
        side_effect=ClientError("upstream failed")
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    assert coordinator.data.schedules == {}


async def test_access_denied_means_no_directives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a device without directive access gets an empty grant, not an error."""
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=PermissionError("directives not granted")
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert coordinator.last_update_success
    assert coordinator.data.resources == {}


async def test_startup_failure_does_not_block_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a failed first fetch leaves the entry loaded and recovers later."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=ClientError("EnergyID briefly unreachable")
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)
    assert not coordinator.last_update_success

    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert set(coordinator.data.resources) == {DIRECTIVE_ID}


async def test_access_granted_after_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test API access granted later is picked up by re-authenticating."""
    resource, schedule = _directive_fixture(good_slots=4)

    coordinator = await _setup_with_directives(hass, mock_config_entry)
    assert coordinator.data.resources == {}

    async def grant_token() -> bool:
        mock_webhook_client.api_access_token = "device-token"
        return True

    mock_webhook_client.authenticate = AsyncMock(side_effect=grant_token)
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    await coordinator.async_refresh()

    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    assert coordinator.data.schedules[DIRECTIVE_ID].current == schedule.data[0]


@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_credentials_start_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    status: int,
) -> None:
    """Test rejected credentials while polling start the reauthentication flow."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    mock_webhook_client.get_directives.side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=status
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_schedule_credentials_start_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    status: int,
) -> None:
    """Test credentials rejected on a schedule start reauthentication."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    mock_webhook_client.get_directive_data.side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=status
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_schedule_server_error_keeps_directive_granted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a server error on one schedule only drops that schedule."""
    resource, _ = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(
        side_effect=ClientResponseError(
            request_info=MagicMock(), history=(), status=500
        )
    )

    coordinator = await _setup_with_directives(hass, mock_config_entry)

    assert coordinator.last_update_success
    assert set(coordinator.data.resources) == {DIRECTIVE_ID}
    assert coordinator.data.schedules == {}
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_unclaimed_device_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a device that is no longer claimed starts reauthentication."""
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    async def lose_claim() -> bool:
        mock_webhook_client.is_claimed = False
        return False

    mock_webhook_client.authenticate = AsyncMock(side_effect=lose_claim)
    mock_webhook_client.get_directives.reset_mock()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    mock_webhook_client.get_directives.assert_not_awaited()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def _lose_claim_and_return_nothing(
    client: MagicMock, *_args: object
) -> list[DirectiveResource]:
    client.is_claimed = False
    return []


async def _lose_claim_and_deny(client: MagicMock, *_args: object) -> NoReturn:
    client.is_claimed = False
    raise PermissionError("The device is not authenticated")


@pytest.mark.parametrize(
    ("method", "lose_claim"),
    [
        pytest.param(
            "get_directives", _lose_claim_and_return_nothing, id="get_directives"
        ),
        pytest.param(
            "get_directives", _lose_claim_and_deny, id="get_directives_denied"
        ),
        pytest.param(
            "get_directive_data", _lose_claim_and_deny, id="get_directive_data"
        ),
    ],
)
async def test_claim_lost_while_polling_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    method: str,
    lose_claim: Callable[..., Awaitable[Any]],
) -> None:
    """Test a claim lost during the client's own re-authentication starts reauth."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    getattr(mock_webhook_client, method).side_effect = partial(
        lose_claim, mock_webhook_client
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_server_error_marks_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test a server error while polling fails the update without reauthentication."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)
    coordinator = await _setup_with_directives(hass, mock_config_entry)

    mock_webhook_client.get_directives.side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=500
    )
    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
