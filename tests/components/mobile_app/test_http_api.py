"""Tests for the mobile_app HTTP API."""

import asyncio
from binascii import unhexlify
from collections.abc import Generator
from http import HTTPStatus
import json
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

from nacl.encoding import Base64Encoder
from nacl.secret import SecretBox
import pytest
from pytest_homeassistant.common import MockUser
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import mobile_app, person
from homeassistant.components.http import KEY_HASS
from homeassistant.components.mobile_app.config_flow import MobileAppFlowHandler
from homeassistant.components.mobile_app.const import (
    CONF_CLOUDHOOK_URL,
    CONF_REMOTE_UI_URL,
    CONF_SECRET,
    DATA_DELETED_IDS,
    DATA_REGISTRATION_LOCK,
    DOMAIN,
)
from homeassistant.components.mobile_app.http_api import RegistrationsView
from homeassistant.components.mobile_app.util import async_create_cloud_hook
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .const import REGISTER, REGISTER_CLEARTEXT, RENDER_TEMPLATE


async def test_registration(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test that registrations happen."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    with patch(
        "homeassistant.components.person.async_add_user_device_tracker",
        spec=True,
    ) as add_user_dev_track:
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )

    assert len(add_user_dev_track.mock_calls) == 1
    assert add_user_dev_track.mock_calls[0][1][1] == hass_admin_user.id
    assert add_user_dev_track.mock_calls[0][1][2] == "device_tracker.test_1"

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()
    assert CONF_WEBHOOK_ID in register_json
    assert CONF_SECRET in register_json

    entries = hass.config_entries.async_entries(DOMAIN)

    assert entries[0].unique_id == "io.homeassistant.mobile_app_test-mock-device-id"
    assert entries[0].data["device_id"] == REGISTER_CLEARTEXT["device_id"]
    assert entries[0].data["app_data"] == REGISTER_CLEARTEXT["app_data"]
    assert entries[0].data["app_id"] == REGISTER_CLEARTEXT["app_id"]
    assert entries[0].data["app_name"] == REGISTER_CLEARTEXT["app_name"]
    assert entries[0].data["app_version"] == REGISTER_CLEARTEXT["app_version"]
    assert entries[0].data["device_name"] == REGISTER_CLEARTEXT["device_name"]
    assert entries[0].data["manufacturer"] == REGISTER_CLEARTEXT["manufacturer"]
    assert entries[0].data["model"] == REGISTER_CLEARTEXT["model"]
    assert entries[0].data["os_name"] == REGISTER_CLEARTEXT["os_name"]
    assert entries[0].data["os_version"] == REGISTER_CLEARTEXT["os_version"]
    assert (
        entries[0].data["supports_encryption"]
        == REGISTER_CLEARTEXT["supports_encryption"]
    )


async def test_registration_again_updates_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an app registering again updates its existing entry."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    sensor = {"name": "Battery State", "state": 100, "type": "sensor"}
    resp = await api_client.post(
        f"/api/webhook/{old_webhook_id}",
        json={"type": "register_sensor", "data": {**sensor, "unique_id": "abcd"}},
    )
    assert resp.status == HTTPStatus.CREATED
    entity_registry.async_update_entity(
        "sensor.test_1_battery_state", name="Phone battery"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, REGISTER_CLEARTEXT["device_id"]), entry.entry_id
    )
    device_registry.async_update_device(device.id, name_by_user="My phone")

    resp = await api_client.post(
        "/api/mobile_app/registrations",
        json={**REGISTER_CLEARTEXT, "device_name": "Test 2"},
    )
    assert resp.status == HTTPStatus.CREATED
    new_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.title == "Test 2"
    assert entry.data[CONF_WEBHOOK_ID] == new_webhook_id
    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == [old_webhook_id]
    assert entity_registry.async_get("device_tracker.test_1")

    # The device is kept with its customization and gets the new name
    assert dr.async_entries_for_config_entry(device_registry, entry.entry_id) == [
        device_registry.async_get(device.id)
    ]
    device = device_registry.async_get(device.id)
    assert device.name == "Test 2"
    assert device.name_by_user == "My phone"
    assert entity_registry.async_get("sensor.test_1_battery_state").device_id == (
        device.id
    )

    # The sensor is moved to the new webhook ID and keeps its customization
    sensor_entry = entity_registry.async_get("sensor.test_1_battery_state")
    assert sensor_entry.unique_id == f"{new_webhook_id}_abcd"
    assert sensor_entry.name == "Phone battery"
    assert hass.states.get("sensor.test_1_battery_state")

    # Registering the sensor again with the new webhook updates the entity
    resp = await api_client.post(
        f"/api/webhook/{new_webhook_id}",
        json={
            "type": "register_sensor",
            "data": {**sensor, "state": 50, "unique_id": "abcd"},
        },
    )
    assert resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()
    assert {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    } == {"device_tracker.test_1", "sensor.test_1_battery_state"}
    assert hass.states.get("sensor.test_1_battery_state").state == "50"


async def test_registration_again_disabled_entry(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test an app registering again for a disabled entry enables it."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )

    resp = await api_client.post(
        "/api/mobile_app/registrations",
        json={**REGISTER_CLEARTEXT, "device_name": "Test 2"},
    )
    assert resp.status == HTTPStatus.CREATED
    new_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]

    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.disabled_by is None
    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == "Test 2"
    assert entry.data[CONF_WEBHOOK_ID] == new_webhook_id
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == [old_webhook_id]

    resp = await api_client.post(
        f"/api/webhook/{new_webhook_id}", json={"type": "get_config", "data": {}}
    )
    assert resp.status == HTTPStatus.OK
    assert (await resp.json())["entities"] == {
        REGISTER_CLEARTEXT["device_id"]: {"disabled": False}
    }


async def test_registration_again_unload_fails(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the old registration is kept if the entry can't be unloaded."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    old_data = dict(entry.data)
    resp = await api_client.post(
        f"/api/webhook/{old_webhook_id}",
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "abcd",
            },
        },
    )
    assert resp.status == HTTPStatus.CREATED

    with patch(
        "homeassistant.components.mobile_app.async_unload_entry",
        side_effect=Exception("Unload failed"),
    ):
        resp = await api_client.post(
            "/api/mobile_app/registrations",
            json={**REGISTER_CLEARTEXT, "device_name": "Test 2"},
        )
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    assert entry.title == "Test 1"
    assert entry.data == old_data
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == []
    assert (
        entity_registry.async_get("sensor.test_1_battery_state").unique_id
        == f"{old_webhook_id}_abcd"
    )

    # The app can keep using the old registration
    resp = await api_client.post(
        f"/api/webhook/{old_webhook_id}", json={"type": "get_config", "data": {}}
    )
    assert resp.status == HTTPStatus.OK
    assert "abcd" in (await resp.json())["entities"]

    # The entry can't be reloaded until Home Assistant is restarted
    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    assert entry.data == old_data


async def test_registration_again_setup_fails(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the old registration is set up again if the new one can't be."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    old_data = dict(entry.data)

    # Only the setup with the new registration fails
    with patch.object(
        mobile_app,
        "async_setup_entry",
        wraps=mobile_app.async_setup_entry,
        side_effect=[Exception("Setup failed"), DEFAULT],
    ):
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == old_data
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == []

    resp = await api_client.post(
        f"/api/webhook/{old_data[CONF_WEBHOOK_ID]}",
        json={"type": "get_config", "data": {}},
    )
    assert resp.status == HTTPStatus.OK


async def test_registration_again_disabled_entry_setup_fails(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test a disabled entry stays disabled if registering again fails."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    old_data = dict(entry.data)
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )

    with patch(
        "homeassistant.components.mobile_app.async_setup_entry",
        side_effect=Exception("Setup failed"),
    ):
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert entry.disabled_by is ConfigEntryDisabler.USER
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.data == old_data


async def test_registration_again_disabled_entry_failed_unload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test registering again for a disabled entry which failed to unload."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    old_data = dict(entry.data)
    with patch(
        "homeassistant.components.mobile_app.async_unload_entry",
        side_effect=Exception("Unload failed"),
    ):
        await hass.config_entries.async_set_disabled_by(
            entry.entry_id, ConfigEntryDisabler.USER
        )
    assert entry.state is ConfigEntryState.FAILED_UNLOAD

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert (await resp.json()) == {"message": "Failed to register the app"}
    assert entry.disabled_by is ConfigEntryDisabler.USER
    assert entry.data == old_data
    # The entities of the disabled entry stay disabled
    assert (
        entity_registry.async_get("device_tracker.test_1").disabled_by
        is er.RegistryEntryDisabler.CONFIG_ENTRY
    )


async def test_registration_again_entry_disabled_during_reload(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test registering again fails if the entry is disabled during the reload."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    old_data = dict(entry.data)

    unload_started = asyncio.Event()
    continue_unload = asyncio.Event()
    original_unload_entry = mobile_app.async_unload_entry

    async def _blocking_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        unload_started.set()
        await continue_unload.wait()
        await original_unload_entry(hass, entry)

    with patch.object(mobile_app, "async_unload_entry", _blocking_unload_entry):
        register_task = asyncio.create_task(
            api_client.post("/api/mobile_app/registrations", json=REGISTER_CLEARTEXT)
        )
        await unload_started.wait()
        disable_task = hass.async_create_task(
            hass.config_entries.async_set_disabled_by(
                entry.entry_id, ConfigEntryDisabler.USER
            )
        )
        continue_unload.set()
        resp = await register_task
        await disable_task

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert entry.disabled_by is ConfigEntryDisabler.USER
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.data == old_data
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == []


async def test_old_cloudhook_not_stored_after_registering_again(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test a cloudhook created for the old webhook is deleted, not stored."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    new_data = dict(entry.data)

    # A cloudhook which was being created for the old webhook completes
    with (
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            return_value="https://hooks.nabu.casa/old",
        ),
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook"
        ) as mock_delete_cloudhook,
    ):
        await async_create_cloud_hook(hass, old_webhook_id, entry)
    assert entry.data == new_data
    mock_delete_cloudhook.assert_called_once_with(hass, old_webhook_id)


async def test_registration_concurrent(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test concurrent registrations of an app are serialized."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    flow_started = asyncio.Event()
    continue_flow = asyncio.Event()
    original_add_device_tracker = person.async_add_user_device_tracker

    async def _blocking_add_device_tracker(
        hass: HomeAssistant, user_id: str, device_tracker_entity_id: str
    ) -> None:
        flow_started.set()
        await continue_flow.wait()
        await original_add_device_tracker(hass, user_id, device_tracker_entity_id)

    with patch.object(
        person, "async_add_user_device_tracker", _blocking_add_device_tracker
    ):
        first_task = asyncio.create_task(
            api_client.post("/api/mobile_app/registrations", json=REGISTER_CLEARTEXT)
        )
        await flow_started.wait()
        # The second registration arrives before the first has created the entry
        second_task = asyncio.create_task(
            api_client.post("/api/mobile_app/registrations", json=REGISTER_CLEARTEXT)
        )
        for _ in range(10):
            await asyncio.sleep(0)

        continue_flow.set()
        responses = [await first_task, await second_task]

    assert [resp.status for resp in responses] == [HTTPStatus.CREATED] * 2
    webhook_ids = {(await resp.json())[CONF_WEBHOOK_ID] for resp in responses}

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert {
        entries[0].data[CONF_WEBHOOK_ID],
        *hass.data[DOMAIN][DATA_DELETED_IDS],
    } == webhook_ids


async def test_registration_again_stale_webhook(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the old webhook rejects requests once the app registered again."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]

    unload_started = asyncio.Event()
    continue_unload = asyncio.Event()
    original_unload_entry = mobile_app.async_unload_entry

    async def _blocking_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        unload_started.set()
        await continue_unload.wait()
        await original_unload_entry(hass, entry)

    with patch.object(mobile_app, "async_unload_entry", _blocking_unload_entry):
        register_task = asyncio.create_task(
            api_client.post(
                "/api/mobile_app/registrations",
                json={**REGISTER_CLEARTEXT, "device_name": "Test 2"},
            )
        )
        await unload_started.wait()

        # The old webhook is still registered, but the entry has the new one
        resp = await api_client.post(
            f"/api/webhook/{old_webhook_id}", json={"type": "get_config", "data": {}}
        )
        assert resp.status == HTTPStatus.GONE

        continue_unload.set()
        resp = await register_task
    assert resp.status == HTTPStatus.CREATED


async def test_registration_again_during_setup(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test an app registering again while its entry is set up waits for the setup."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    setup_started = asyncio.Event()
    continue_setup = asyncio.Event()
    original_setup_entry = mobile_app.async_setup_entry

    async def _blocking_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        setup_started.set()
        await continue_setup.wait()
        await original_setup_entry(hass, entry)

    with patch.object(mobile_app, "async_setup_entry", _blocking_setup_entry):
        reload_task = hass.async_create_task(
            hass.config_entries.async_reload(entry.entry_id)
        )
        await setup_started.wait()
        assert entry.state is ConfigEntryState.SETUP_IN_PROGRESS

        register_task = asyncio.create_task(
            api_client.post("/api/mobile_app/registrations", json=REGISTER_CLEARTEXT)
        )
        for _ in range(10):
            await asyncio.sleep(0)
        assert not register_task.done()

        continue_setup.set()
        assert await reload_task
        resp = await register_task

    assert resp.status == HTTPStatus.CREATED
    new_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_WEBHOOK_ID] == new_webhook_id
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == [old_webhook_id]


async def test_registration_again_request_cancelled(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test a registration is completed if its request is cancelled."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    unload_started = asyncio.Event()
    continue_unload = asyncio.Event()
    original_unload_entry = mobile_app.async_unload_entry

    async def _blocking_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        unload_started.set()
        await continue_unload.wait()
        await original_unload_entry(hass, entry)

    request = MagicMock()
    request.app = {KEY_HASS: hass}
    request.json = AsyncMock(
        return_value={**REGISTER_CLEARTEXT, "device_name": "Test 2"}
    )
    request.__getitem__.side_effect = {"hass_user": hass_admin_user}.__getitem__

    with patch.object(mobile_app, "async_unload_entry", _blocking_unload_entry):
        post_task = asyncio.create_task(RegistrationsView().post(request))
        await unload_started.wait()
        post_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await post_task

        continue_unload.set()
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == "Test 2"
    assert entry.data[CONF_WEBHOOK_ID] != old_webhook_id
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == [old_webhook_id]
    assert not hass.data[DOMAIN][DATA_REGISTRATION_LOCK].locked()


async def test_webhook_command_keeps_registration(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    hass_read_only_access_token: str,
) -> None:
    """Test a webhook command uses its registration if the app registers again."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]

    command_started = asyncio.Event()
    continue_command = asyncio.Event()

    async def _blocking_instance_id(hass: HomeAssistant) -> str:
        command_started.set()
        await continue_command.wait()
        return "mock-instance-id"

    with (
        patch(
            "homeassistant.components.mobile_app.webhook.instance_id.async_get",
            _blocking_instance_id,
        ),
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch("homeassistant.components.cloud.async_is_connected", return_value=False),
        patch(
            "homeassistant.components.cloud.async_remote_ui_url",
            return_value="https://remote.ui",
        ),
        patch(
            "homeassistant.components.mobile_app.webhook.async_is_local_only_user",
            return_value=False,
        ) as mock_is_local_only_user,
    ):
        command_task = asyncio.create_task(
            api_client.post(
                f"/api/webhook/{old_webhook_id}",
                json={"type": "get_config", "data": {}},
            )
        )
        await command_started.wait()

        # Another user registers the app again while the command is handled
        read_only_client = await hass_client(hass_read_only_access_token)
        resp = await read_only_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )
        assert resp.status == HTTPStatus.CREATED

        continue_command.set()
        resp = await command_task

    assert resp.status == HTTPStatus.OK
    mock_is_local_only_user.assert_called_once_with(hass, hass_admin_user.id)


@pytest.fixture
def mock_delete_cloudhook() -> Generator[MagicMock]:
    """Mock a connected cloud which creates a cloudhook for each webhook."""

    async def _get_or_create_cloudhook(_hass: HomeAssistant, webhook_id: str) -> str:
        return f"https://hooks.nabu.casa/{webhook_id}"

    with (
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            side_effect=_get_or_create_cloudhook,
        ),
        patch(
            "homeassistant.components.cloud.async_listen_cloudhook_change",
            return_value=lambda: None,
        ),
        patch(
            "homeassistant.components.cloud.async_remote_ui_url",
            return_value="https://remote.ui",
        ),
        patch("homeassistant.components.cloud.async_delete_cloudhook") as mock_delete,
    ):
        yield mock_delete


async def test_registration_again_deletes_old_cloudhook(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_delete_cloudhook: MagicMock,
) -> None:
    """Test an app registering again deletes the cloudhook of the old webhook."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data[CONF_CLOUDHOOK_URL] == f"https://hooks.nabu.casa/{old_webhook_id}"

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    new_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]

    mock_delete_cloudhook.assert_called_once_with(hass, old_webhook_id)
    assert entry.data[CONF_CLOUDHOOK_URL] == f"https://hooks.nabu.casa/{new_webhook_id}"


async def test_registration_again_old_cloudhook_deletion_fails(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_delete_cloudhook: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failing to delete the old cloudhook doesn't fail the registration."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    mock_delete_cloudhook.side_effect = TimeoutError
    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    new_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]

    mock_delete_cloudhook.assert_called_once_with(hass, old_webhook_id)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_WEBHOOK_ID] == new_webhook_id
    assert hass.data[DOMAIN][DATA_DELETED_IDS] == [old_webhook_id]
    assert "Error retiring the old webhook of Test 1" in caplog.text


async def test_registration_again_fails_deletes_new_cloudhook(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_delete_cloudhook: MagicMock,
) -> None:
    """Test a failed registration deletes the cloudhook of the new webhook."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    old_webhook_id = (await resp.json())[CONF_WEBHOOK_ID]
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(
        "homeassistant.components.mobile_app.async_setup_entry",
        side_effect=Exception("Setup failed"),
    ):
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR

    assert mock_delete_cloudhook.call_count == 1
    new_webhook_id = mock_delete_cloudhook.call_args.args[1]
    assert new_webhook_id != old_webhook_id
    assert entry.data[CONF_WEBHOOK_ID] == old_webhook_id
    assert entry.data[CONF_CLOUDHOOK_URL] == f"https://hooks.nabu.casa/{old_webhook_id}"


async def test_registration_flow_abort(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_delete_cloudhook: MagicMock,
) -> None:
    """Test an aborted registration flow returns an error and deletes the cloudhook."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    async def _abort_registration(
        self: MobileAppFlowHandler, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        return self.async_abort(reason="already_configured")

    with patch.object(
        MobileAppFlowHandler, "async_step_registration", _abort_registration
    ):
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert mock_delete_cloudhook.call_count == 1


async def test_registration_flow_aborts_for_existing_entry(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the registration flow doesn't replace an existing entry."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    api_client = await hass_client()

    resp = await api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )
    assert resp.status == HTTPStatus.CREATED
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=dict(REGISTER_CLEARTEXT), context={"source": "registration"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


async def test_registration_encryption(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that registrations happen."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    resp = await api_client.post("/api/mobile_app/registrations", json=REGISTER)

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()

    key = unhexlify(register_json[CONF_SECRET])

    payload = json.dumps(RENDER_TEMPLATE["data"]).encode("utf-8")

    data = SecretBox(key).encrypt(payload, encoder=Base64Encoder).decode("utf-8")

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await api_client.post(
        f"/api/webhook/{register_json[CONF_WEBHOOK_ID]}", json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = SecretBox(key).decrypt(
        webhook_json["encrypted_data"], encoder=Base64Encoder
    )
    decrypted_data = decrypted_data.decode("utf-8")

    assert json.loads(decrypted_data) == {"one": "Hello world"}


@pytest.mark.parametrize(
    "cloud_is_connected",
    [
        True,
        False,
    ],
)
async def test_registration_with_cloud(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    cloud_is_connected: bool,
) -> None:
    """Test that cloudhook_url is only returned when cloud is connected."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    cloudhook_url = "https://hooks.nabu.casa/test123"

    with (
        patch(
            "homeassistant.components.mobile_app.http_api.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mobile_app.http_api.cloud.async_is_connected",
            return_value=cloud_is_connected,
        ),
        patch(
            "homeassistant.components.mobile_app.http_api.async_create_cloud_hook",
            return_value=cloudhook_url,
        ),
        patch(
            "homeassistant.components.mobile_app.http_api.cloud.async_remote_ui_url",
            return_value="https://remote.ui",
        ),
        patch(
            "homeassistant.components.person.async_add_user_device_tracker",
            spec=True,
        ),
    ):
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()
    assert CONF_WEBHOOK_ID in register_json

    assert register_json.get(CONF_CLOUDHOOK_URL) == (
        cloudhook_url if cloud_is_connected else None
    )


async def test_registration_with_cloud_local_only_user(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test cloudhook_url and remote_ui_url not returned for local users."""
    hass_admin_user.local_only = True
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    with (
        patch(
            "homeassistant.components.mobile_app.http_api.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mobile_app.http_api.cloud.async_is_connected",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mobile_app.http_api.async_create_cloud_hook",
            return_value="https://hooks.nabu.casa/test123",
        ) as mock_create_cloud_hook,
        patch(
            "homeassistant.components.mobile_app.http_api.cloud.async_remote_ui_url",
            return_value="https://remote.ui",
        ),
        patch(
            "homeassistant.components.person.async_add_user_device_tracker",
            spec=True,
        ),
    ):
        resp = await api_client.post(
            "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
        )

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()
    assert register_json.get(CONF_CLOUDHOOK_URL) is None
    assert register_json.get(CONF_REMOTE_UI_URL) is None
    mock_create_cloud_hook.assert_not_called()


async def test_registration_encryption_legacy(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test that registrations happen."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    api_client = await hass_client()

    resp = await api_client.post("/api/mobile_app/registrations", json=REGISTER)

    assert resp.status == HTTPStatus.CREATED
    register_json = await resp.json()

    keylen = SecretBox.KEY_SIZE
    key = register_json[CONF_SECRET].encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b"\0")

    payload = json.dumps(RENDER_TEMPLATE["data"]).encode("utf-8")

    data = SecretBox(key).encrypt(payload, encoder=Base64Encoder).decode("utf-8")

    container = {"type": "render_template", "encrypted": True, "encrypted_data": data}

    resp = await api_client.post(
        f"/api/webhook/{register_json[CONF_WEBHOOK_ID]}", json=container
    )

    assert resp.status == HTTPStatus.OK

    webhook_json = await resp.json()
    assert "encrypted_data" in webhook_json

    decrypted_data = SecretBox(key).decrypt(
        webhook_json["encrypted_data"], encoder=Base64Encoder
    )
    decrypted_data = decrypted_data.decode("utf-8")

    assert json.loads(decrypted_data) == {"one": "Hello world"}
