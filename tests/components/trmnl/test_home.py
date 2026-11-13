"""Tests for sending the home to TRMNL."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.plugins import AiohttpClientMocker
from trmnl.exceptions import TRMNLError, TRMNLForbiddenError, TRMNLNotFoundError
from trmnl.models import PluginSetting

from homeassistant.components.trmnl.const import (
    CONF_HOME_ENTITIES,
    CONF_HOME_PLUGIN_SETTING_ID,
    CONF_MESSAGES_PLUGIN_SETTING_ID,
    DOMAIN,
    HOMEY_PLUGIN_ID,
    OAUTH2_TOKEN,
)
from homeassistant.components.trmnl.home import build_snapshot, capabilities_of
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import OAuth2TokenRequestConnectionError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from . import setup_integration


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            State(
                "sensor.t",
                "21.0",
                {"device_class": "temperature", "unit_of_measurement": "°C"},
            ),
            {"measure_temperature": {"value": 21, "units": "°C"}},
        ),
        (
            State(
                "sensor.p",
                "12.5",
                {"device_class": "power", "unit_of_measurement": "W"},
            ),
            {"measure_power": {"value": 12.5, "units": "W"}},
        ),
        (State("sensor.t", "unknown", {"device_class": "temperature"}), {}),
        (State("sensor.t", "abc", {"device_class": "temperature"}), {}),
        (State("sensor.x", "1", {"device_class": "duration"}), {}),
        (
            State("binary_sensor.m", "on", {"device_class": "motion"}),
            {"alarm_motion": {"value": True}},
        ),
        (
            State("light.l", "on", {"brightness": 255}),
            {"onoff": {"value": True}, "dim": {"value": 1.0}},
        ),
        (State("light.l", "unavailable"), {}),
        (
            State(
                "climate.c", "heat", {"current_temperature": 19.5, "temperature": 21}
            ),
            {
                "measure_temperature": {"value": 19.5, "units": "°C"},
                "target_temperature": {"value": 21, "units": "°C"},
                "thermostat_mode": {"value": "heat"},
            },
        ),
        (
            State("cover.g", "closed", {"device_class": "garage"}),
            {"garagedoor_closed": {"value": True}},
        ),
        (
            State("cover.b", "open", {"current_position": 40}),
            {"windowcoverings_set": {"value": 0.4}},
        ),
        (State("cover.b", "open"), {}),
        (State("lock.d", "unlocked"), {"locked": {"value": False}}),
        (
            State("alarm_control_panel.a", "armed_away"),
            {"homealarm_state": {"value": "armed"}},
        ),
        (State("camera.c", "idle"), {}),
    ],
)
def test_capabilities_of(state: State, expected: dict) -> None:
    """Test each kind of entity maps to the capabilities TRMNL draws."""
    assert capabilities_of(state, UnitOfTemperature.CELSIUS) == expected


async def test_snapshot_groups_entities_by_device_and_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities of one device become one TRMNL device, naming only its area."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    kitchen = area_registry.async_create("Kitchen")
    area_registry.async_create("Bedroom")
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "1")}, name="Thermostat"
    )
    device_registry.async_update_device(device.id, area_id=kitchen.id)
    for object_id, value, device_class in (
        ("temp", "20", "temperature"),
        ("temp_floor", "18", "temperature"),
        ("hum", "40", "humidity"),
        ("power", "unknown", "power"),
    ):
        entity_registry.async_get_or_create(
            "sensor",
            "test",
            object_id,
            device_id=device.id,
            suggested_object_id=object_id,
        )
        hass.states.async_set(
            f"sensor.{object_id}", value, {"device_class": device_class}
        )

    snapshot = build_snapshot(
        hass, ["sensor.temp", "sensor.temp_floor", "sensor.hum", "sensor.power"]
    )

    assert snapshot["zone_names"] == {kitchen.id: "Kitchen"}
    assert snapshot["devices"] == [
        {
            "name": "Thermostat",
            "zone": "Kitchen",
            "available": True,
            "klass": "sensor",
            "capabilities": {
                "measure_temperature": {"value": 20},
                "measure_temperature.2": {"value": 18},
                "measure_humidity": {"value": 40},
            },
        }
    ]


async def test_snapshot_sends_only_picked_entities(hass: HomeAssistant) -> None:
    """Test entities the user did not pick, or that are gone, are not sent."""
    hass.states.async_set("light.picked", "on")
    hass.states.async_set("light.not_picked", "on")

    names = [
        device["name"]
        for device in build_snapshot(hass, ["light.picked", "light.removed"])["devices"]
    ]

    assert names == ["picked"]


async def test_snapshot_names_a_nameless_device_after_its_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity on a device with no name is sent with the entity's name."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "1")}
    )
    device_registry.async_update_device(device.id, name=None)
    entity_registry.async_get_or_create(
        "light", "test", "lamp", device_id=device.id, suggested_object_id="lamp"
    )
    hass.states.async_set("light.lamp", "on", {"friendly_name": "Desk lamp"})

    assert build_snapshot(hass, ["light.lamp"])["devices"][0]["name"] == "Desk lamp"


async def test_snapshot_puts_a_child_device_in_its_parent_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity on a child device with no area of its own takes the parent's area."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    kitchen = area_registry.async_create("Kitchen")
    parent = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "hub")}, name="Hub"
    )
    device_registry.async_update_device(parent.id, area_id=kitchen.id)
    child = device_registry.async_get_or_create_child(
        config_entry_id=entry.entry_id,
        identifiers={("test", "lamp")},
        name="Lamp",
        parent_device_id=parent.id,
    )
    entity_registry.async_get_or_create(
        "light", "test", "lamp", device_id=child.id, suggested_object_id="lamp"
    )
    hass.states.async_set("light.lamp", "on")

    snapshot = build_snapshot(hass, ["light.lamp"])

    assert (snapshot["zone_names"], snapshot["devices"][0]["zone"]) == (
        {kitchen.id: "Kitchen"},
        "Kitchen",
    )


@pytest.fixture
def home_entry(mock_config_entry: MockConfigEntry) -> MockConfigEntry:
    """Config entry that shows one lamp on TRMNL."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=mock_config_entry.unique_id,
        data=mock_config_entry.data,
        options={CONF_HOME_ENTITIES: ["light.lamp"]},
    )


async def test_nothing_sent_until_entities_are_picked(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry with no picked entities creates and sends nothing."""
    hass.states.async_set("light.lamp", "on")

    await setup_integration(hass, mock_config_entry)

    mock_trmnl_client.create_plugin_setting.assert_not_awaited()
    mock_trmnl_client.update_plugin_setting_data.assert_not_awaited()


async def test_setup_creates_plugin_setting_and_pushes(
    hass: HomeAssistant, mock_trmnl_client: AsyncMock, home_entry: MockConfigEntry
) -> None:
    """Test the first setup creates the plugin setting once and pushes the home."""
    mock_trmnl_client.create_plugin_setting.return_value = PluginSetting(
        identifier=42, name="Home", plugin_id=HOMEY_PLUGIN_ID
    )
    hass.states.async_set("light.lamp", "on")

    await setup_integration(hass, home_entry)

    mock_trmnl_client.create_plugin_setting.assert_awaited_once_with(
        hass.config.location_name, HOMEY_PLUGIN_ID
    )
    assert home_entry.options[CONF_HOME_PLUGIN_SETTING_ID] == 42
    plugin_setting_id, snapshot = (
        mock_trmnl_client.update_plugin_setting_data.await_args.args
    )
    assert (plugin_setting_id, snapshot["devices"][0]["capabilities"]) == (
        42,
        {"onoff": {"value": True}},
    )


async def test_change_pushes_once_after_cooldown(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a burst of changes makes one push a minute later, and no change makes none."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)
    mock_trmnl_client.update_plugin_setting_data.reset_mock()

    hass.states.async_set("light.lamp", "off")
    hass.states.async_set("light.lamp", "on")
    hass.states.async_set("light.lamp", "off")
    hass.states.async_set("light.not_picked", "on")
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 0

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1


async def test_timer_and_change_share_one_cooldown(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the timer does not push while a change push waits, and they share one push."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)
    freezer.tick(timedelta(minutes=4, seconds=30))
    async_fire_time_changed(hass)
    hass.states.async_set("light.lamp", "off")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 2


async def test_burst_after_cooldown_waits_and_pushes_once(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a burst of changes on an idle pusher waits a minute and pushes the last state once."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    hass.states.async_set("light.lamp", "off", {"brightness": 10})
    hass.states.async_set("light.lamp", "on", {"brightness": 255})
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 2
    snapshot = mock_trmnl_client.update_plugin_setting_data.await_args.args[1]
    assert snapshot["devices"][0]["capabilities"]["dim"] == {"value": 1.0}


async def test_slow_push_does_not_overlap_the_next(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the minute between sends starts when a slow push finishes."""
    created = asyncio.Event()

    async def create_plugin_setting(*_: Any) -> PluginSetting:
        await created.wait()
        return PluginSetting(identifier=42, name="Home", plugin_id=HOMEY_PLUGIN_ID)

    mock_trmnl_client.create_plugin_setting.side_effect = create_plugin_setting
    hass.states.async_set("light.lamp", "on")
    home_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(home_entry.entry_id)
    hass.states.async_set("light.lamp", "off")
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    created.set()
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_trmnl_client.create_plugin_setting.assert_awaited_once()
    assert [
        call.args[0]
        for call in mock_trmnl_client.update_plugin_setting_data.await_args_list
    ] == [42, 42]


async def test_remove_during_first_push_deletes_the_new_plugin_setting(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
) -> None:
    """Test removing the entry waits for a push under way, so its plugin setting is deleted."""
    created = asyncio.Event()

    async def create_plugin_setting(*_: Any) -> PluginSetting:
        await created.wait()
        return PluginSetting(identifier=42, name="Home", plugin_id=HOMEY_PLUGIN_ID)

    mock_trmnl_client.create_plugin_setting.side_effect = create_plugin_setting
    hass.states.async_set("light.lamp", "on")
    home_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(home_entry.entry_id)

    remove = hass.async_create_task(
        hass.config_entries.async_remove(home_entry.entry_id)
    )
    await asyncio.sleep(0)
    created.set()
    await remove

    mock_trmnl_client.delete_plugin_setting.assert_awaited_once_with(42)


async def test_remove_waits_for_a_push_past_the_unload_task_timeout(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removal waits for a push itself, and nothing is sent after it."""
    created = asyncio.Event()

    async def create_plugin_setting(*_: Any) -> PluginSetting:
        await created.wait()
        return PluginSetting(identifier=42, name="Home", plugin_id=HOMEY_PLUGIN_ID)

    mock_trmnl_client.create_plugin_setting.side_effect = create_plugin_setting
    hass.states.async_set("light.lamp", "on")
    home_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(home_entry.entry_id)
    wait = asyncio.wait

    async def give_up_at_once(tasks: Any, timeout: float | None = None) -> Any:
        # Only the config entry's 10 second wait for its tasks gives up at once.
        return await wait(tasks, timeout=0 if timeout == 10 else timeout)

    hass.states.async_set("light.lamp", "off")
    await asyncio.sleep(0)
    with patch("homeassistant.config_entries.asyncio.wait", give_up_at_once):
        remove = hass.async_create_task(
            hass.config_entries.async_remove(home_entry.entry_id)
        )
        for _ in range(20):
            await asyncio.sleep(0)
        assert not remove.done()
        created.set()
        await remove
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_trmnl_client.delete_plugin_setting.assert_awaited_once_with(42)
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1


async def test_unload_survives_a_token_refresh_failing_under_way(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unload waits for a push whose token refresh fails, logs it and unloads."""
    release = asyncio.Event()

    async def fail_refresh() -> None:
        await release.wait()
        raise OAuth2TokenRequestConnectionError(domain=DOMAIN)

    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    with patch.object(
        home_entry.runtime_data, "async_ensure_token_valid", side_effect=fail_refresh
    ):
        hass.states.async_set("light.lamp", "off")
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await asyncio.sleep(0)
        unload = hass.async_create_task(
            hass.config_entries.async_unload(home_entry.entry_id)
        )
        await asyncio.sleep(0)
        release.set()
        assert await unload

    assert home_entry.state is ConfigEntryState.NOT_LOADED
    assert "Could not send the home to TRMNL" in caplog.text


async def test_failed_push_is_retried_on_the_next_tick(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed push logs a warning and the same snapshot is sent again later."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    hass.states.async_set("light.lamp", "on")
    mock_trmnl_client.update_plugin_setting_data.side_effect = [
        TRMNLError("Request failed with status 429."),
        None,
    ]

    await setup_integration(hass, home_entry)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "status 429" in caplog.text
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 2


async def test_deleted_plugin_setting_is_made_again(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
) -> None:
    """Test a plugin setting the user deleted on TRMNL is created again and pushed to."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    mock_trmnl_client.create_plugin_setting.return_value = PluginSetting(
        identifier=43, name="Home", plugin_id=HOMEY_PLUGIN_ID
    )
    mock_trmnl_client.update_plugin_setting_data.side_effect = [
        TRMNLNotFoundError("Plugin setting not found"),
        None,
    ]
    hass.states.async_set("light.lamp", "on")

    await setup_integration(hass, home_entry)

    assert home_entry.options[CONF_HOME_PLUGIN_SETTING_ID] == 43
    assert mock_trmnl_client.update_plugin_setting_data.await_args.args[0] == 43


async def test_push_refused_for_scope_starts_reauth_once_and_stops(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a push refused for a revoked content scope starts reauth once and stops pushing."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    mock_trmnl_client.update_plugin_setting_data.side_effect = TRMNLForbiddenError(
        "Missing capability: content"
    )
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    for state in ("off", "on"):
        hass.states.async_set("light.lamp", state)
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1
    assert [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == [SOURCE_REAUTH]
    assert caplog.text.count("Missing capability: content") == 1


async def test_change_during_refused_push_is_not_sent(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a change waiting behind a push that TRMNL refuses for its scope is dropped."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    refuse = asyncio.Event()

    async def update_plugin_setting_data(*_: Any) -> None:
        await refuse.wait()
        raise TRMNLForbiddenError("Missing capability: content")

    mock_trmnl_client.update_plugin_setting_data.side_effect = (
        update_plugin_setting_data
    )
    hass.states.async_set("light.lamp", "on")
    await hass.config_entries.async_setup(home_entry.entry_id)
    hass.states.async_set("light.lamp", "off")
    await asyncio.sleep(0)

    refuse.set()
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1


async def test_last_entity_removed_clears_the_plugin(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unpicking every entity sends an empty home to the plugin it made."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=mock_config_entry.unique_id,
        data=mock_config_entry.data,
        options={CONF_HOME_ENTITIES: [], CONF_HOME_PLUGIN_SETTING_ID: 42},
    )

    await setup_integration(hass, entry)

    plugin_setting_id, snapshot = (
        mock_trmnl_client.update_plugin_setting_data.await_args.args
    )
    assert (plugin_setting_id, snapshot["devices"]) == (42, [])


@pytest.mark.parametrize(
    ("scope", "deleted"),
    [("openid read devices content delete", True), ("openid read devices", False)],
)
async def test_remove_entry_deletes_plugin_setting_when_allowed(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    scope: str,
    deleted: bool,
) -> None:
    """Test removing the entry deletes the home plugin setting only with the delete scope."""
    token = {**home_entry.data["token"], "scope": scope}
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={**home_entry.data, "token": token},
        options={CONF_HOME_PLUGIN_SETTING_ID: 42, CONF_MESSAGES_PLUGIN_SETTING_ID: 7},
    )
    await setup_integration(hass, entry)

    await hass.config_entries.async_remove(entry.entry_id)

    assert mock_trmnl_client.delete_plugin_setting.await_args_list == (
        [call(42), call(7)] if deleted else []
    )


async def test_remove_entry_deletes_the_rest_when_one_is_gone(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a plugin setting the user already deleted does not stop the next delete."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=home_entry.data,
        options={CONF_HOME_PLUGIN_SETTING_ID: 42, CONF_MESSAGES_PLUGIN_SETTING_ID: 7},
    )
    mock_trmnl_client.delete_plugin_setting.side_effect = [
        TRMNLNotFoundError("Plugin setting not found"),
        None,
    ]
    await setup_integration(hass, entry)

    await hass.config_entries.async_remove(entry.entry_id)

    assert mock_trmnl_client.delete_plugin_setting.await_args_list == [
        call(42),
        call(7),
    ]
    assert "Could not delete" not in caplog.text


async def test_remove_entry_refreshes_an_expired_token_without_saving_it(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal refreshes an expired token for the delete, though the entry is gone."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=home_entry.data,
        options={CONF_HOME_PLUGIN_SETTING_ID: 42},
    )
    await setup_integration(hass, entry)
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "token": {**entry.data["token"], "expires_at": 0}},
    )
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )

    with patch(
        "homeassistant.components.trmnl.TRMNLClient", return_value=mock_trmnl_client
    ) as client_class:
        await hass.config_entries.async_remove(entry.entry_id)

    assert client_class.call_args.kwargs["token"] == "new-access"
    mock_trmnl_client.delete_plugin_setting.assert_awaited_once_with(42)
    assert "Error calling entry remove callback" not in caplog.text


async def test_remove_entry_logs_failed_delete_and_deletes_the_rest(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed delete on removal is logged and the next plugin is still deleted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=mock_config_entry.data,
        options={CONF_HOME_PLUGIN_SETTING_ID: 42, CONF_MESSAGES_PLUGIN_SETTING_ID: 7},
    )
    mock_trmnl_client.delete_plugin_setting.side_effect = [
        TRMNLError("status 500"),
        None,
    ]
    await setup_integration(hass, entry)

    await hass.config_entries.async_remove(entry.entry_id)

    assert mock_trmnl_client.delete_plugin_setting.await_args_list == [
        call(42),
        call(7),
    ]
    assert "Could not delete TRMNL plugin setting 42: status 500" in caplog.text


async def test_remove_entry_logs_failed_token_refresh(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a token refresh that fails on removal is logged and deletes nothing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=home_entry.data,
        options={CONF_HOME_PLUGIN_SETTING_ID: 42},
    )
    await setup_integration(hass, entry)
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, "token": {**entry.data["token"], "expires_at": 0}},
    )
    aioclient_mock.post(OAUTH2_TOKEN, status=500)

    await hass.config_entries.async_remove(entry.entry_id)

    mock_trmnl_client.delete_plugin_setting.assert_not_called()
    assert "Could not delete the TRMNL plugin settings" in caplog.text
