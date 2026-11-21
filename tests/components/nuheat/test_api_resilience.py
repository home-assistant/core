"""Cooldown, deadline and permission behavior with synthetic requests only."""

import asyncio
from asyncio import CancelledError, Event, create_task, sleep
from collections.abc import Awaitable, Callable
from copy import deepcopy
import time
from unittest.mock import AsyncMock, patch

from chemelex_nuheat import NuHeatPermissionError, NuHeatRateLimitError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.nuheat import climate
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.components.nuheat.coordinator import NuHeatCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later

from .control_helpers import CONTROLS, advance, command
from .helpers import FakeOAuthImplementation, complete_oauth_flow, jwt_access_token
from .test_integration import (
    ACCOUNT_SUBJECT,
    coordinator_with,
    oauth_data,
    oauth_implementation,
    thermostat,
)
from .test_migration import create_customized_registry_records
from .test_permanent_hold import permanent


@pytest.mark.parametrize("provider", ["community", "custom"])
async def test_permission_failure_during_reauth_keeps_entry_and_registries(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    provider: str,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Permission failure during reauth keeps entry and registries."""
    entry = MockConfigEntry(
        domain="nuheat",
        version=3,
        unique_id=ACCOUNT_SUBJECT,
        data={**oauth_data(), "auth_implementation": provider},
        options={"synthetic": "kept"},
    )
    entry.add_to_hass(hass)
    create_customized_registry_records(hass, entry, "ABC123")
    entities = dict(entity_registry.entities)
    devices = deepcopy(list(device_registry.devices))
    original = deepcopy(dict(entry.data))
    with patch(
        "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
        AsyncMock(side_effect=NuHeatPermissionError("synthetic", status=403)),
    ):
        result = await complete_oauth_flow(
            hass,
            hass_client_no_auth,
            oauth_implementation(domain=provider),
            entry=entry,
            confirmation_step="reauth_confirm",
        )
    assert result["reason"] == "permission_denied"
    assert dict(entry.data) == original and entry.options == {"synthetic": "kept"}
    assert list(hass.config_entries.async_entries("nuheat")) == [entry]
    assert dict(entity_registry.entities) == entities
    assert list(device_registry.devices) == devices


async def _never_returns(*_args: object, **_kwargs: object) -> None:
    """Stall a synthetic token validation until its operation budget expires."""
    await Event().wait()


@pytest.mark.parametrize(
    ("error", "token_effect"),
    [
        pytest.param(
            NuHeatPermissionError("synthetic", status=403), None, id="permission"
        ),
        pytest.param(NuHeatRateLimitError(120), None, id="throttle"),
        pytest.param(NuHeatRateLimitError(120), _never_returns, id="token-timeout"),
    ],
)
async def test_startup_failures_preserve_entry_and_retry(
    hass: HomeAssistant,
    error: NuHeatPermissionError | NuHeatRateLimitError,
    token_effect: Callable[..., Awaitable[None]] | None,
) -> None:
    """Startup failures retain the existing entry for a later retry."""
    entry = MockConfigEntry(
        domain="nuheat",
        version=3,
        unique_id="synthetic-account-subject",
        data={
            "auth_implementation": "test",
            "token": {
                "access_token": jwt_access_token(),
                "refresh_token": "synthetic",
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
            },
        },
    )
    entry.add_to_hass(hass)
    original = dict(entry.data)

    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            AsyncMock(return_value=FakeOAuthImplementation()),
        ),
        patch(
            "homeassistant.components.nuheat.timeout", lambda _: asyncio.timeout(0.01)
        ),
        patch(
            "homeassistant.components.nuheat.NuHeatClient.list_thermostats",
            AsyncMock(side_effect=error),
        ),
        patch(
            "homeassistant.components.nuheat.OAuth2Session.async_ensure_token_valid",
            AsyncMock(side_effect=token_effect),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert dict(entry.data) == original


async def test_zero_retry_after_does_not_create_endless_fast_reads(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Zero retry after does not create endless fast reads."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.list_thermostats.side_effect = NuHeatRateLimitError(0)
    coordinator.async_schedule_reconciliation()
    await advance(hass, freezer, 2)
    reads = api.list_thermostats.await_count
    await advance(hass, freezer, 30)
    assert api.list_thermostats.await_count == reads
    await coordinator.async_shutdown()


async def test_very_long_cooldown_read_is_cancelled_on_shutdown(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Very long cooldown read is cancelled on shutdown."""
    coordinator, api, _ = await coordinator_with(hass, thermostat())
    api.cooldown_remaining = 31536000000.0
    coordinator.async_schedule_reconciliation()
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    await advance(hass, freezer, 86401)
    assert api.list_thermostats.await_count == reads


@pytest.mark.parametrize("control", [*CONTROLS, "target"])
async def test_all_controls_reject_cooldown_without_writes(
    hass: HomeAssistant, control: str
) -> None:
    """All controls reject cooldown without writes."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.cooldown_remaining = 120.0
    with pytest.raises(ServiceValidationError) as error:
        await _command(entity, control)
    assert error.value.translation_key == "rate_limited"
    api.set_target_temperature.assert_not_awaited()
    api.set_schedule_mode.assert_not_awaited()
    api.set_standby.assert_not_awaited()
    assert not entity.assumed_state
    await coordinator.async_shutdown()


@pytest.mark.parametrize("control", [*CONTROLS, "target"])
async def test_all_controls_timeout_without_retry_and_release_lock(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, control: str
) -> None:
    """All controls timeout without retry and release lock."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")

    async def hang(*args: object, **kwargs: object) -> None:
        """Hang."""
        await Event().wait()

    api.set_schedule_mode.side_effect = hang
    api.set_target_temperature.side_effect = hang
    api.set_standby.side_effect = hang
    monkeypatch.setattr(climate, "CONTROL_OPERATION_TIMEOUT", 0.01)
    with pytest.raises(HomeAssistantError) as error:
        await _command(entity, control)
    assert error.value.translation_key == "request_timeout"
    assert not entity._setpoint_lock.locked() and not entity._control_tasks
    assert not entity.assumed_state
    assert (
        api.set_target_temperature.await_count
        + api.set_schedule_mode.await_count
        + api.set_standby.await_count
        == 1
    )
    await coordinator.async_shutdown()


async def test_lock_wait_timeout_does_not_send_queued_command(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lock wait timeout does not send queued command."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    await entity._setpoint_lock.acquire()
    monkeypatch.setattr(climate, "CONTROL_OPERATION_TIMEOUT", 0.01)
    try:
        with pytest.raises(HomeAssistantError):
            await entity.async_set_preset_mode("run_schedule")
    finally:
        entity._setpoint_lock.release()
    api.set_schedule_mode.assert_not_awaited()
    assert not entity._control_tasks
    await coordinator.async_shutdown()


async def test_unload_cancels_control_without_new_reads(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Unload cancels control without new reads."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    entered = Event()

    async def hang(*args: object, **kwargs: object) -> None:
        """Hang."""
        entered.set()
        await Event().wait()

    api.set_target_temperature.side_effect = hang
    pending = create_task(entity.async_set_temperature(temperature=24))
    await entered.wait()
    await entity.async_will_remove_from_hass()
    with pytest.raises(CancelledError):
        await pending
    reads = api.list_thermostats.await_count
    await coordinator.async_shutdown()
    await advance(hass, freezer, 360)
    assert api.list_thermostats.await_count == reads
    assert not entity._control_tasks and not entity._setpoint_lock.locked()


async def test_primary_permission_is_not_account_reauth(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Primary permission is not account reauth."""
    coordinator, api, entry = await coordinator_with(hass, permanent())
    original = dict(entry.data)
    api.list_thermostats.side_effect = NuHeatPermissionError("synthetic", status=403)
    coordinator.async_schedule_reconciliation()
    await advance(hass, freezer, 2)
    assert not isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert "permission" in str(coordinator.last_exception)
    assert dict(entry.data) == original
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    api.set_schedule_mode.side_effect = NuHeatPermissionError("synthetic", status=403)
    with pytest.raises(ServiceValidationError) as error:
        await entity.async_set_preset_mode("Permanent Hold")
    assert error.value.translation_key == "permission_denied"
    api.set_target_temperature.assert_not_awaited()
    await coordinator.async_shutdown()


async def test_rate_limit_after_accepted_write_is_uncertain_not_rejected(
    hass: HomeAssistant,
) -> None:
    """Rate limit after accepted write is uncertain not rejected."""
    coordinator, api, _ = await coordinator_with(hass, permanent())
    entity = NuHeatClimateEntity(coordinator, "ABC123")
    error = NuHeatRateLimitError(120)
    error.write_applied = True
    api.set_target_temperature.side_effect = error
    with pytest.raises(HomeAssistantError) as raised:
        await entity.async_set_temperature(temperature=24)
    assert raised.value.translation_key == "write_unconfirmed"
    assert not entity.assumed_state
    api.set_target_temperature.assert_awaited_once()
    await coordinator.async_shutdown()


async def _command(entity: NuHeatClimateEntity, control: str) -> None:
    """Dispatch a synthetic control through its ordinary public method."""
    if control == "target":
        await entity.async_set_temperature(temperature=24)
    else:
        await command(entity, control)


async def _trigger_scheduled_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    coordinator: NuHeatCoordinator,
    is_poll: bool,
) -> None:
    """Deliver due poll or command-reconciliation callbacks through HA's clock."""
    if is_poll:
        async_call_later(hass, 2, coordinator._handle_refresh_interval)
    else:
        coordinator.async_schedule_reconciliation()
    freezer.tick(2)
    async_fire_time_changed(hass)
    await sleep(0)


@pytest.mark.parametrize("serial", ["ABC123", "XYZ789"])
async def test_account_cooldown_covers_devices_without_blocking_other_accounts(
    hass: HomeAssistant, serial: str
) -> None:
    """Two devices share their account quota while another account stays usable."""
    coordinator, api, _ = await coordinator_with(
        hass, thermostat(), thermostat("XYZ789")
    )
    other, other_api, _ = await coordinator_with(hass, thermostat("OTHER123"))
    api.cooldown_remaining = 120.0
    blocked = NuHeatClimateEntity(coordinator, serial)
    available = NuHeatClimateEntity(other, "OTHER123")
    with pytest.raises(ServiceValidationError) as error:
        await blocked.async_set_temperature(temperature=24)
    assert error.value.translation_key == "rate_limited"
    api.set_target_temperature.assert_not_awaited()
    await available.async_set_temperature(temperature=24)
    other_api.set_target_temperature.assert_awaited_once()
    assert other.cooldown_remaining == 0.0
    await coordinator.async_shutdown()
    await other.async_shutdown()
