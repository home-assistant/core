"""Tests for sending the home to TRMNL."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.plugins import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion
from trmnl.exceptions import (
    TRMNLAuthenticationError,
    TRMNLError,
    TRMNLForbiddenError,
    TRMNLNotFoundError,
    TRMNLRateLimitError,
)
from trmnl.models import PluginSetting

from homeassistant.components.trmnl.const import (
    CONF_HOME_ENTITIES,
    CONF_HOME_PLUGIN_SETTING_ID,
    DOMAIN,
    OAUTH2_TOKEN,
    PLUGIN_KEYNAME,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from . import setup_integration

PLUGIN_SETTING = PluginSetting(identifier=42, name="Home", plugin_id=452)


@pytest.fixture
def home_entry(mock_config_entry: MockConfigEntry) -> MockConfigEntry:
    """Return an entry that shows the lamp and already has its plugin setting."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=mock_config_entry.unique_id,
        data={**mock_config_entry.data, CONF_HOME_PLUGIN_SETTING_ID: 42},
        options={CONF_HOME_ENTITIES: ["light.lamp"]},
    )


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Move past the push cooldown."""
    freezer.tick(timedelta(seconds=91))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


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


async def test_setup_creates_plugin_setting_and_pushes_the_home(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the first push creates the plugin setting and sends each entity with its area."""
    mock_trmnl_client.create_plugin_setting.return_value = PLUGIN_SETTING
    other_entry = MockConfigEntry(domain="test")
    other_entry.add_to_hass(hass)
    kitchen = area_registry.async_create("Kitchen")
    bedroom = area_registry.async_create("Bedroom")
    area_registry.async_create("Garage")
    hub = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("test", "hub")}
    )
    device_registry.async_update_device(hub.id, area_id=kitchen.id)
    child = device_registry.async_get_or_create_child(
        config_entry_id=other_entry.entry_id,
        identifiers={("test", "child")},
        parent_device_id=hub.id,
    )
    entity_registry.async_get_or_create(
        "sensor", "test", "temp", device_id=child.id, suggested_object_id="temp"
    )
    lamp = entity_registry.async_get_or_create(
        "light", "test", "lamp", suggested_object_id="lamp"
    )
    entity_registry.async_update_entity(lamp.entity_id, area_id=bedroom.id)
    hass.states.async_set(
        "sensor.temp",
        "21.5",
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )
    hass.states.async_set(
        "light.lamp", "on", {"brightness": 128, "friendly_name": "Desk lamp"}
    )
    hass.states.async_set(
        "climate.hall",
        "heat",
        {"current_temperature": 66, "temperature": 70, "temperature_unit": "°F"},
    )
    hass.states.async_set("light.not_picked", "on")
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=mock_config_entry.unique_id,
        data=mock_config_entry.data,
        options={
            CONF_HOME_ENTITIES: [
                "sensor.temp",
                "light.lamp",
                "climate.hall",
                "light.removed",
            ]
        },
    )

    await setup_integration(hass, entry)

    mock_trmnl_client.create_plugin_setting.assert_awaited_once_with(
        hass.config.location_name, plugin_keyname=PLUGIN_KEYNAME
    )
    assert entry.data[CONF_HOME_PLUGIN_SETTING_ID] == 42
    assert mock_trmnl_client.update_plugin_setting_data.await_args.args == snapshot


async def test_changes_push_at_most_once_per_cooldown(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test changes in the cooldown after a push share one push, and no change sends none."""
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    for state in ("off", "on", "off"):
        hass.states.async_set("light.lamp", state)
    hass.states.async_set("light.not_picked", "on")
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1

    await tick(hass, freezer)
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 2
    assert (
        mock_trmnl_client.update_plugin_setting_data.await_args.args[1]["entities"][0][
            "state"
        ]
        == "off"
    )

    hass.states.async_set("light.lamp", "off", {"effect": "rainbow"})
    await tick(hass, freezer)
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 2


@pytest.mark.parametrize(
    "error",
    [
        TRMNLError("status 500"),
        TRMNLRateLimitError("Rate limit exceeded", None),
        ClientError("Connection reset"),
        TimeoutError(),
        OAuth2TokenRequestConnectionError(domain=DOMAIN),
    ],
)
async def test_failed_push_is_retried_with_the_current_home(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Test a failed push logs once and is retried after the cooldown with no change needed."""
    mock_trmnl_client.update_plugin_setting_data.side_effect = [error, error, None]
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)
    hass.states.async_set("light.lamp", "off")

    for _ in range(3):
        await tick(hass, freezer)

    assert mock_trmnl_client.update_plugin_setting_data.await_count == 3
    assert (
        mock_trmnl_client.update_plugin_setting_data.await_args.args[1]["entities"][0][
            "state"
        ]
        == "off"
    )
    assert caplog.text.count("Could not send the home to TRMNL") == 1
    assert "Sent the home to TRMNL again" in caplog.text


async def test_rate_limited_push_waits_as_long_as_trmnl_asks(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a 429 with Retry-After holds every push, a change too, until that time has passed."""
    mock_trmnl_client.update_plugin_setting_data.side_effect = [
        TRMNLRateLimitError("Rate limit exceeded", 600),
        None,
    ]
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    hass.states.async_set("light.lamp", "off")
    await tick(hass, freezer)
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1

    freezer.tick(timedelta(seconds=600))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 2
    assert (
        mock_trmnl_client.update_plugin_setting_data.await_args.args[1]["entities"][0][
            "state"
        ]
        == "off"
    )


async def test_unload_cancels_a_pending_retry(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a retry waiting when the entry unloads is never sent."""
    mock_trmnl_client.update_plugin_setting_data.side_effect = TimeoutError()
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    await hass.config_entries.async_unload(home_entry.entry_id)
    await tick(hass, freezer)

    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1


async def test_change_during_a_slow_push_is_sent_after_it(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a change whose cooldown ends while a push still runs is sent once that push ends."""
    release = asyncio.Event()
    calls: list[str] = []

    async def update_plugin_setting_data(_: int, home: dict[str, Any]) -> None:
        calls.append(home["entities"][0]["state"])
        if len(calls) == 1:
            await release.wait()

    mock_trmnl_client.update_plugin_setting_data.side_effect = (
        update_plugin_setting_data
    )
    hass.states.async_set("light.lamp", "on")
    home_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(home_entry.entry_id)
    hass.states.async_set("light.lamp", "off")
    freezer.tick(timedelta(seconds=91))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)

    release.set()
    await hass.async_block_till_done()
    await tick(hass, freezer)

    assert calls == ["on", "off"]


async def test_successful_push_sends_no_retry(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a push that succeeds after a failure leaves no retry behind."""
    mock_trmnl_client.update_plugin_setting_data.side_effect = [TimeoutError(), None]
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    hass.states.async_set("light.lamp", "off")
    for _ in range(3):
        await tick(hass, freezer)

    assert mock_trmnl_client.update_plugin_setting_data.await_count == 2


async def test_area_moves_and_renames_are_pushed(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test moving the parent device, the device or the entity, and renaming the area, each push."""
    other_entry = MockConfigEntry(domain="test")
    other_entry.add_to_hass(hass)
    hub = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("test", "hub")}
    )
    lamp = device_registry.async_get_or_create_child(
        config_entry_id=other_entry.entry_id,
        identifiers={("test", "lamp")},
        parent_device_id=hub.id,
    )
    entity_registry.async_get_or_create(
        "light",
        "test",
        "lamp",
        suggested_object_id="lamp",
        device_id=lamp.id,
        original_name="Lamp",
    )
    kitchen = area_registry.async_create("Kitchen")
    hall = area_registry.async_create("Hall")
    bedroom = area_registry.async_create("Bedroom")
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("test", "other")}
    )
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    device_registry.async_update_device(other_device.id, area_id=hall.id)
    await tick(hass, freezer)
    device_registry.async_update_device(hub.id, area_id=kitchen.id)
    await tick(hass, freezer)
    area_registry.async_update(kitchen.id, name="Galley")
    await tick(hass, freezer)
    device_registry.async_update_child_device(lamp.id, area_id=hall.id)
    await tick(hass, freezer)
    entity_registry.async_update_entity("light.lamp", area_id=bedroom.id)
    await tick(hass, freezer)

    assert [
        call.args[1]["areas"]
        for call in mock_trmnl_client.update_plugin_setting_data.await_args_list
    ] == [
        {},
        {kitchen.id: "Kitchen"},
        {kitchen.id: "Galley"},
        {hall.id: "Hall"},
        {bedroom.id: "Bedroom"},
    ]


@pytest.mark.parametrize(
    "error",
    [
        OAuth2TokenRequestReauthError(domain=DOMAIN, request_info=Mock(), status=400),
        TRMNLAuthenticationError("Request failed with status 401."),
        TRMNLForbiddenError("Missing capability: content"),
    ],
)
async def test_refused_push_starts_reauth_and_stops(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Test a refused sign in or scope starts reauth and sends nothing more until reload."""
    mock_trmnl_client.update_plugin_setting_data.side_effect = error
    hass.states.async_set("light.lamp", "on")
    await setup_integration(hass, home_entry)

    hass.states.async_set("light.lamp", "off")
    await tick(hass, freezer)

    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1
    assert [
        flow["context"]["source"] for flow in hass.config_entries.flow.async_progress()
    ] == [SOURCE_REAUTH]


async def test_deleted_plugin_setting_is_made_again(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
) -> None:
    """Test a plugin setting the user deleted on TRMNL is created again and pushed to."""
    mock_trmnl_client.create_plugin_setting.return_value = PluginSetting(
        identifier=43, name="Home", plugin_id=452
    )
    mock_trmnl_client.update_plugin_setting_data.side_effect = [
        TRMNLNotFoundError("Plugin setting not found"),
        None,
    ]
    hass.states.async_set("light.lamp", "on")

    await setup_integration(hass, home_entry)

    assert home_entry.data[CONF_HOME_PLUGIN_SETTING_ID] == 43
    assert mock_trmnl_client.update_plugin_setting_data.await_args.args[0] == 43


async def test_last_entity_removed_clears_the_home(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
) -> None:
    """Test unpicking every entity sends an empty home to the plugin setting it made."""
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(home_entry, options={CONF_HOME_ENTITIES: []})

    await setup_integration(hass, home_entry)

    mock_trmnl_client.update_plugin_setting_data.assert_awaited_once_with(
        42, {"areas": {}, "entities": []}
    )


async def test_remove_waits_for_the_push_under_way(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removal waits past the unload task timeout for the first push, so its plugin setting is deleted."""
    created = asyncio.Event()

    async def create_plugin_setting(*_: Any, **__: Any) -> PluginSetting:
        await created.wait()
        return PLUGIN_SETTING

    mock_trmnl_client.create_plugin_setting.side_effect = create_plugin_setting
    hass.states.async_set("light.lamp", "on")
    home_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        home_entry,
        data={
            key: value
            for key, value in home_entry.data.items()
            if key != CONF_HOME_PLUGIN_SETTING_ID
        },
    )
    await hass.config_entries.async_setup(home_entry.entry_id)
    hass.states.async_set("light.lamp", "off")
    wait = asyncio.wait

    async def give_up_at_once(tasks: Any, timeout: float | None = None) -> Any:
        # Only the config entry's 10 second wait for its tasks gives up at once.
        return await wait(tasks, timeout=0 if timeout == 10 else timeout)

    with patch("homeassistant.config_entries.asyncio.wait", give_up_at_once):
        remove = hass.async_create_task(
            hass.config_entries.async_remove(home_entry.entry_id)
        )
        for _ in range(20):
            await asyncio.sleep(0)
        assert not remove.done()
        created.set()
        await remove
    await tick(hass, freezer)

    mock_trmnl_client.delete_plugin_setting.assert_awaited_once_with(42)
    assert mock_trmnl_client.update_plugin_setting_data.await_count == 1


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
        domain=DOMAIN, version=2, data={**home_entry.data, "token": token}
    )
    await setup_integration(hass, entry)

    await hass.config_entries.async_remove(entry.entry_id)

    assert mock_trmnl_client.delete_plugin_setting.await_count == int(deleted)


async def test_remove_entry_refreshes_an_expired_token_without_saving_it(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal refreshes an expired token for the delete, though the entry is gone."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=home_entry.data)
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


@pytest.mark.parametrize("error", [TRMNLError("status 500"), TimeoutError()])
async def test_remove_entry_logs_failed_delete(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    home_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Test a failed delete on removal is logged and does not block the removal."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=home_entry.data)
    mock_trmnl_client.delete_plugin_setting.side_effect = error
    await setup_integration(hass, entry)

    await hass.config_entries.async_remove(entry.entry_id)

    mock_trmnl_client.delete_plugin_setting.assert_awaited_once_with(42)
    assert "Could not delete the TRMNL home plugin setting" in caplog.text
