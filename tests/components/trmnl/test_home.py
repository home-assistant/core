"""Tests for sending the home to TRMNL."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from trmnl.exceptions import TRMNLError, TRMNLForbiddenError, TRMNLNotFoundError
from trmnl.models import PluginSetting

from homeassistant.components.trmnl.const import (
    CONF_HOME_ENTITIES,
    CONF_HOME_PLUGIN_SETTING_ID,
    DOMAIN,
    HOMEY_PLUGIN_ID,
)
from homeassistant.components.trmnl.home import build_snapshot, capabilities_of
from homeassistant.core import HomeAssistant, State
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
                "measure_temperature": {"value": 19.5},
                "target_temperature": {"value": 21},
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
    assert capabilities_of(state) == expected


async def test_snapshot_groups_entities_by_device_and_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities of one device become one TRMNL device in its area."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    kitchen = area_registry.async_create("Kitchen")
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


async def test_push_without_content_scope_explains_it(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test TRMNL refusing the push for a missing scope tells the user to sign in again."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry, options={**home_entry.options, CONF_HOME_PLUGIN_SETTING_ID: 42}
    )
    mock_trmnl_client.update_plugin_setting_data.side_effect = TRMNLForbiddenError(
        "Missing capability: content"
    )
    hass.states.async_set("light.lamp", "on")

    await setup_integration(hass, home_entry)

    assert "Missing capability: content" in caplog.text
    assert "Sign in again" in caplog.text


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
        options={CONF_HOME_PLUGIN_SETTING_ID: 42},
    )
    await setup_integration(hass, entry)

    await hass.config_entries.async_remove(entry.entry_id)

    assert mock_trmnl_client.delete_plugin_setting.await_count == int(deleted)


async def test_remove_entry_logs_failed_delete(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed delete on removal is logged and does not block the removal."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=mock_config_entry.data,
        options={CONF_HOME_PLUGIN_SETTING_ID: 42},
    )
    mock_trmnl_client.delete_plugin_setting.side_effect = TRMNLError("status 404")
    await setup_integration(hass, entry)

    await hass.config_entries.async_remove(entry.entry_id)

    mock_trmnl_client.delete_plugin_setting.assert_awaited_once_with(42)
    assert "Could not delete the TRMNL home plugin setting" in caplog.text
