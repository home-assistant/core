"""Tests for EnergyID directive sensors."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
from energyid_webhooks.directives import (
    DirectiveData,
    DirectiveResource,
    DirectiveSignal,
    SignalProvider,
)
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.energyid.const import CONF_ENABLE_DIRECTIVES
from homeassistant.components.energyid.coordinator import DIRECTIVE_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


def _directive_fixture(
    good_slots: int = 1,
) -> tuple[DirectiveResource, DirectiveData]:
    """Return a directive with 15 minute slots: good ones first, then a neutral one."""
    slot_start = dt_util.utcnow().replace(second=0, microsecond=0) - dt.timedelta(
        minutes=5
    )
    resource = DirectiveResource(
        id="11111111-1111-1111-1111-111111111111",
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


async def test_directive_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an exposed directive becomes a translated enum sensor."""
    resource, schedule = _directive_fixture()
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 1
    state = hass.states.get(entries[0].entity_id)
    assert state is not None
    assert state.state == "very_good_moment"
    assert state.attributes["next_state"] == "neutral"
    assert state.attributes["next_change"] == schedule.data[1].timestamp.isoformat()
    assert "options" in state.attributes
    assert "very_bad_moment" in state.attributes["options"]


async def test_multiple_directive_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test every directive exposed to the device becomes its own sensor."""
    first_resource, first_schedule = _directive_fixture()
    second_resource = DirectiveResource(
        id="22222222-2222-2222-2222-222222222222",
        title="Grid planner",
        description="Public energy planner",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="energyid",
            display_name="EnergyID",
            logo_url=None,
        ),
    )
    second_schedule = DirectiveData(
        title=second_resource.title,
        description=second_resource.description,
        interval="PT15M",
        data=(
            DirectiveSignal(
                timestamp=first_schedule.data[0].timestamp,
                signal="--",
                color="#cc0f0f",
                raw_value=0,
            ),
        ),
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        return_value=[first_resource, second_resource]
    )
    mock_webhook_client.get_directive_data = AsyncMock(
        side_effect=lambda directive_id: (
            first_schedule if directive_id == first_resource.id else second_schedule
        )
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries} == {
        f"{mock_config_entry.entry_id}_{first_resource.id}",
        f"{mock_config_entry.entry_id}_{second_resource.id}",
    }
    states = {
        entry.unique_id: state
        for entry in entries
        if (state := hass.states.get(entry.entity_id)) is not None
    }
    assert (
        states[f"{mock_config_entry.entry_id}_{first_resource.id}"].state
        == "very_good_moment"
    )
    assert (
        states[f"{mock_config_entry.entry_id}_{second_resource.id}"].state
        == "very_bad_moment"
    )


async def test_directive_requires_opt_in(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an authorized directive is not exposed until selected."""
    resource, schedule = _directive_fixture()
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mock_webhook_client.get_directives.assert_not_awaited()
    mock_webhook_client.get_directive_data.assert_not_awaited()


async def test_directive_grant_appears_without_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a directive granted after setup is discovered by the coordinator."""
    resource, schedule = _directive_fixture()
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives.return_value = [resource]
    mock_webhook_client.get_directive_data.return_value = schedule

    await mock_config_entry.runtime_data.directive_coordinator.async_refresh()
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 1
    state = hass.states.get(entries[0].entity_id)
    assert state is not None
    assert state.state == "very_good_moment"


async def test_unavailable_directive_does_not_block_other_directives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test one failing upstream signal does not block healthy signals."""
    resource, schedule = _directive_fixture()
    unavailable_resource = DirectiveResource(
        id="22222222-2222-2222-2222-222222222222",
        title="Unavailable planner",
        description="Broken upstream",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="provider-2",
            display_name="Provider 2",
            logo_url=None,
        ),
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        return_value=[unavailable_resource, resource]
    )

    async def get_directive_data(directive_id: str) -> DirectiveData:
        if directive_id == unavailable_resource.id:
            raise ClientError("upstream failed")
        return schedule

    mock_webhook_client.get_directive_data = AsyncMock(side_effect=get_directive_data)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 2
    states = {
        entry.unique_id: state.state
        for entry in entries
        if (state := hass.states.get(entry.entity_id)) is not None
    }
    assert (
        states[f"{mock_config_entry.entry_id}_{unavailable_resource.id}"]
        == STATE_UNAVAILABLE
    )
    assert states[f"{mock_config_entry.entry_id}_{resource.id}"] == "very_good_moment"


async def test_registry_preserved_when_startup_fetch_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a transient startup failure does not delete registry entries."""
    resource, _ = _directive_fixture()
    registry_entry = entity_registry.async_get_or_create(
        "sensor",
        "energyid",
        f"{mock_config_entry.entry_id}_{resource.id}",
        config_entry=mock_config_entry,
        suggested_object_id="my_customized_directive",
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=ClientError("EnergyID briefly unreachable")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    preserved = entity_registry.async_get(registry_entry.entity_id)
    assert preserved is not None
    assert preserved.unique_id == f"{mock_config_entry.entry_id}_{resource.id}"


async def test_revoked_directive_removed_and_regrant_rediscovered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a revoked directive is pruned and a re-granted one reappears."""
    first_resource, first_schedule = _directive_fixture()
    second_resource = DirectiveResource(
        id="22222222-2222-2222-2222-222222222222",
        title="Second planner",
        description="Second planner",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="provider-2",
            display_name="Provider 2",
            logo_url=None,
        ),
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        return_value=[first_resource, second_resource]
    )
    mock_webhook_client.get_directive_data = AsyncMock(return_value=first_schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 2
    )

    mock_webhook_client.get_directives.return_value = [first_resource]
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries} == {
        f"{mock_config_entry.entry_id}_{first_resource.id}"
    }

    mock_webhook_client.get_directives.return_value = [
        first_resource,
        second_resource,
    ]
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.unique_id for entry in entries} == {
        f"{mock_config_entry.entry_id}_{first_resource.id}",
        f"{mock_config_entry.entry_id}_{second_resource.id}",
    }


async def test_directive_access_granted_after_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test API access granted later is picked up by re-authenticating."""
    resource, schedule = _directive_fixture(good_slots=4)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # The next poll re-authenticates but access is still not granted.
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    async def grant_token() -> bool:
        mock_webhook_client.api_access_token = "device-token"
        return True

    mock_webhook_client.authenticate = AsyncMock(side_effect=grant_token)
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 1
    state = hass.states.get(entries[0].entity_id)
    assert state is not None
    assert state.state == "very_good_moment"


async def test_directive_without_current_signal_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a schedule that only covers the future gives an unknown state."""
    resource, schedule = _directive_fixture()
    future_schedule = DirectiveData(
        title=schedule.title,
        description=schedule.description,
        interval=schedule.interval,
        data=(schedule.data[1],),
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=future_schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [registry_entry] = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    state = hass.states.get(registry_entry.entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["next_state"] == "neutral"
    assert state.attributes["next_change"] == schedule.data[1].timestamp.isoformat()


async def test_directive_unavailable_while_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed poll marks the sensor unavailable until the next success."""
    resource, schedule = _directive_fixture(good_slots=4)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    [registry_entry] = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert hass.states.get(registry_entry.entity_id).state == "very_good_moment"

    mock_webhook_client.get_directives.side_effect = ClientError("EnergyID down")
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(registry_entry.entity_id).state == STATE_UNAVAILABLE
    assert entity_registry.async_get(registry_entry.entity_id) is not None

    mock_webhook_client.get_directives.side_effect = None
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(registry_entry.entity_id).state == "very_good_moment"


async def test_directive_access_denied(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device without directive access gets no sensors and no error."""
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=PermissionError("directives not granted")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_stale_directive_pruned_once_grants_are_known(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stale entity survives a failed startup fetch but not an empty grant."""
    stale_entry = entity_registry.async_get_or_create(
        "sensor",
        "energyid",
        f"{mock_config_entry.entry_id}_revoked",
        config_entry=mock_config_entry,
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        side_effect=ClientError("EnergyID briefly unreachable")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(stale_entry.entity_id) is not None

    mock_webhook_client.get_directives = AsyncMock(return_value=[])
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entity_registry.async_get(stale_entry.entity_id) is None


async def test_granted_directive_with_failing_schedule_is_discovered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a newly granted directive appears even while its schedule fails."""
    resource, schedule = _directive_fixture()
    failing_resource = DirectiveResource(
        id="22222222-2222-2222-2222-222222222222",
        title="Unavailable planner",
        description="Broken upstream",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="provider-2",
            display_name="Provider 2",
            logo_url=None,
        ),
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async def get_directive_data(directive_id: str) -> DirectiveData:
        if directive_id == failing_resource.id:
            raise ClientError("upstream failed")
        return schedule

    mock_webhook_client.get_directives.return_value = [resource, failing_resource]
    mock_webhook_client.get_directive_data = AsyncMock(side_effect=get_directive_data)
    freezer.tick(DIRECTIVE_UPDATE_INTERVAL + dt.timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    states = {
        registry_entry.unique_id: state.state
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if (state := hass.states.get(registry_entry.entity_id)) is not None
    }
    assert (
        states[f"{mock_config_entry.entry_id}_{failing_resource.id}"]
        == STATE_UNAVAILABLE
    )
    assert states[f"{mock_config_entry.entry_id}_{resource.id}"] == "very_good_moment"


async def test_directive_expires_after_its_last_slot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a schedule whose last slot has ended no longer reports a signal."""
    resource, schedule = _directive_fixture()
    expired_schedule = DirectiveData(
        title=schedule.title,
        description=schedule.description,
        interval=schedule.interval,
        data=(
            DirectiveSignal(
                timestamp=dt_util.utcnow() - dt.timedelta(hours=3),
                signal="++",
                color="#00750e",
                raw_value=0,
            ),
        ),
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=expired_schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [registry_entry] = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    state = hass.states.get(registry_entry.entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["next_change"] is None
