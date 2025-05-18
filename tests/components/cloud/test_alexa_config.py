"""Test Alexa config."""

import contextlib
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.alexa import errors
from homeassistant.components.cloud import ALEXA_SCHEMA, alexa_config
from homeassistant.components.cloud.const import (
    DATA_CLOUD,
    PREF_ALEXA_DEFAULT_EXPOSE,
    PREF_ALEXA_ENTITY_CONFIGS,
    PREF_SHOULD_EXPOSE,
)
from homeassistant.components.cloud.prefs import CloudPreferences
from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
    async_expose_entity,
    async_get_entity_settings,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EntityCategory,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def cloud_stub() -> Mock:
    """Stub the cloud."""
    return Mock(is_logged_in=True, subscription_expired=False)


def expose_new(hass: HomeAssistant, expose_new: bool) -> None:
    """Enable exposing new entities to Alexa."""
    exposed_entities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities("cloud.alexa", expose_new)


def expose_entity(hass: HomeAssistant, entity_id: str, should_expose: bool) -> None:
    """Expose an entity to Alexa."""
    async_expose_entity(hass, "cloud.alexa", entity_id, should_expose)


async def test_alexa_config_expose_entity_prefs(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    cloud_stub: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Alexa config should expose using prefs."""
    assert await async_setup_component(hass, "homeassistant", {})
    entity_entry1 = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_config_id",
        suggested_object_id="config_light",
        entity_category=EntityCategory.CONFIG,
    )
    entity_entry2 = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_diagnostic_id",
        suggested_object_id="diagnostic_light",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    entity_entry3 = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_hidden_integration_id",
        suggested_object_id="hidden_integration_light",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    entity_entry4 = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_hidden_user_id",
        suggested_object_id="hidden_user_light",
        hidden_by=er.RegistryEntryHider.USER,
    )
    entity_entry5 = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_basement_id",
        suggested_object_id="basement",
    )
    entity_entry6 = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_entrance_id",
        suggested_object_id="entrance",
    )

    await cloud_prefs.async_update(
        alexa_enabled=True,
        alexa_report_state=False,
    )
    expose_new(hass, True)
    expose_entity(hass, entity_entry5.entity_id, False)
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )
    await conf.async_initialize()

    # an entity which is not in the entity registry can be exposed
    expose_entity(hass, "light.kitchen", True)
    assert conf.should_expose("light.kitchen")
    # categorized and hidden entities should not be exposed
    assert not conf.should_expose(entity_entry1.entity_id)
    assert not conf.should_expose(entity_entry2.entity_id)
    assert not conf.should_expose(entity_entry3.entity_id)
    assert not conf.should_expose(entity_entry4.entity_id)
    # this has been hidden
    assert not conf.should_expose(entity_entry5.entity_id)
    # exposed by default
    assert conf.should_expose(entity_entry6.entity_id)

    expose_entity(hass, entity_entry5.entity_id, True)
    assert conf.should_expose(entity_entry5.entity_id)

    expose_entity(hass, entity_entry5.entity_id, None)
    assert not conf.should_expose(entity_entry5.entity_id)

    assert "alexa" not in hass.config.components
    await hass.async_block_till_done()
    assert "alexa" in hass.config.components
    assert not conf.should_expose(entity_entry5.entity_id)


async def test_alexa_config_report_state(
    hass: HomeAssistant, cloud_prefs: CloudPreferences, cloud_stub: Mock
) -> None:
    """Test Alexa config should expose using prefs."""
    assert await async_setup_component(hass, "homeassistant", {})

    await cloud_prefs.async_update(
        alexa_report_state=False,
    )
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )
    await conf.async_initialize()
    await conf.set_authorized(True)

    assert cloud_prefs.alexa_report_state is False
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False

    with patch.object(conf, "async_get_access_token", AsyncMock(return_value="hello")):
        await cloud_prefs.async_update(alexa_report_state=True)
        await hass.async_block_till_done()

    assert cloud_prefs.alexa_report_state is True
    assert conf.should_report_state is True
    assert conf.is_reporting_states is True

    await cloud_prefs.async_update(alexa_report_state=False)
    await hass.async_block_till_done()

    assert cloud_prefs.alexa_report_state is False
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False


async def test_alexa_config_invalidate_token(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test Alexa config should expose using prefs."""
    assert await async_setup_component(hass, "homeassistant", {})

    aioclient_mock.post(
        "https://example/alexa/access_token",
        json={
            "access_token": "mock-token",
            "event_endpoint": "http://example.com/alexa_endpoint",
            "expires_in": 30,
        },
    )
    conf = alexa_config.CloudAlexaConfig(
        hass,
        ALEXA_SCHEMA({}),
        "mock-user-id",
        cloud_prefs,
        Mock(
            servicehandlers_server="example",
            auth=Mock(async_check_token=AsyncMock()),
            websession=async_get_clientsession(hass),
        ),
    )

    token = await conf.async_get_access_token()
    assert token == "mock-token"
    assert len(aioclient_mock.mock_calls) == 1

    token = await conf.async_get_access_token()
    assert token == "mock-token"
    assert len(aioclient_mock.mock_calls) == 1
    assert conf._token_valid is not None
    conf.async_invalidate_access_token()
    assert conf._token_valid is None
    token = await conf.async_get_access_token()
    assert token == "mock-token"
    assert len(aioclient_mock.mock_calls) == 2


@pytest.mark.parametrize(
    ("reject_reason", "expected_exception"),
    [
        ("RefreshTokenNotFound", errors.RequireRelink),
        ("UnknownRegion", errors.RequireRelink),
        ("OtherReason", errors.NoTokenAvailable),
    ],
)
async def test_alexa_config_fail_refresh_token(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    reject_reason: str,
    expected_exception: type[Exception],
) -> None:
    """Test Alexa config failing to refresh token."""
    assert await async_setup_component(hass, "homeassistant", {})
    # Enable exposing new entities to Alexa
    expose_new(hass, True)
    # Register a fan entity
    entity_entry = entity_registry.async_get_or_create(
        "fan", "test", "unique", suggested_object_id="test_fan"
    )

    aioclient_mock.post(
        "https://example/alexa/access_token",
        json={
            "access_token": "mock-token",
            "event_endpoint": "http://example.com/alexa_endpoint",
            "expires_in": 30,
        },
    )
    aioclient_mock.post("http://example.com/alexa_endpoint", text="", status=202)
    await cloud_prefs.async_update(
        alexa_report_state=False,
    )
    conf = alexa_config.CloudAlexaConfig(
        hass,
        ALEXA_SCHEMA({}),
        "mock-user-id",
        cloud_prefs,
        Mock(
            servicehandlers_server="example",
            auth=Mock(async_check_token=AsyncMock()),
            websession=async_get_clientsession(hass),
        ),
    )
    await conf.async_initialize()
    await conf.set_authorized(True)

    assert cloud_prefs.alexa_report_state is False
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False

    hass.states.async_set(entity_entry.entity_id, "off")

    # Enable state reporting
    await cloud_prefs.async_update(alexa_report_state=True)
    await hass.async_block_till_done()

    assert cloud_prefs.alexa_report_state is True
    assert conf.should_report_state is True
    assert conf.is_reporting_states is True

    # Change states to trigger event listener
    hass.states.async_set(entity_entry.entity_id, "on")
    await hass.async_block_till_done()

    # Invalidate the token and try to fetch another
    conf.async_invalidate_access_token()
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://example/alexa/access_token",
        json={"reason": reject_reason},
        status=400,
    )

    # Change states to trigger event listener
    hass.states.async_set(entity_entry.entity_id, "off")
    await hass.async_block_till_done()

    # Check state reporting is still wanted in cloud prefs, but disabled for Alexa
    assert cloud_prefs.alexa_report_state is True
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False

    # Simulate we're again authorized, but token update fails
    with pytest.raises(expected_exception):
        await conf.set_authorized(True)

    assert cloud_prefs.alexa_report_state is True
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False

    # Simulate we're again authorized and token update succeeds
    # State reporting should now be re-enabled for Alexa
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://example/alexa/access_token",
        json={
            "access_token": "mock-token",
            "event_endpoint": "http://example.com/alexa_endpoint",
            "expires_in": 30,
        },
    )
    await conf.set_authorized(True)
    assert cloud_prefs.alexa_report_state is True
    assert conf.should_report_state is True
    assert conf.is_reporting_states is True


@contextlib.contextmanager
def patch_sync_helper():
    """Patch sync helper."""
    to_update = []
    to_remove = []

    def sync_helper(to_upd, to_rem):
        to_update.extend([ent_id for ent_id in to_upd if ent_id not in to_update])
        to_remove.extend([ent_id for ent_id in to_rem if ent_id not in to_remove])
        return True

    with (
        patch("homeassistant.components.cloud.alexa_config.SYNC_DELAY", 0),
        patch(
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig._sync_helper",
            side_effect=sync_helper,
        ),
    ):
        yield to_update, to_remove


async def test_alexa_update_expose_trigger_sync(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    cloud_prefs: CloudPreferences,
    cloud_stub: Mock,
) -> None:
    """Test Alexa config responds to updating exposed entities."""
    assert await async_setup_component(hass, "homeassistant", {})
    # Enable exposing new entities to Alexa
    expose_new(hass, True)
    # Register entities
    binary_sensor_entry = entity_registry.async_get_or_create(
        "binary_sensor", "test", "unique", suggested_object_id="door"
    )
    sensor_entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique", suggested_object_id="temp"
    )
    light_entry = entity_registry.async_get_or_create(
        "light", "test", "unique", suggested_object_id="kitchen"
    )

    hass.states.async_set(binary_sensor_entry.entity_id, "on")
    hass.states.async_set(
        sensor_entry.entity_id,
        "23",
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )
    hass.states.async_set(light_entry.entity_id, "off")

    await cloud_prefs.async_update(
        alexa_enabled=True,
        alexa_report_state=False,
    )
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )
    await conf.async_initialize()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    with patch_sync_helper() as (to_update, to_remove):
        expose_entity(hass, light_entry.entity_id, True)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done()

    assert conf._alexa_sync_unsub is None
    assert to_update == [light_entry.entity_id]
    assert to_remove == []

    with patch_sync_helper() as (to_update, to_remove):
        expose_entity(hass, light_entry.entity_id, False)
        expose_entity(hass, binary_sensor_entry.entity_id, True)
        expose_entity(hass, sensor_entry.entity_id, True)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done()

    assert conf._alexa_sync_unsub is None
    assert sorted(to_update) == [binary_sensor_entry.entity_id, sensor_entry.entity_id]
    assert to_remove == [light_entry.entity_id]

    with patch_sync_helper() as (to_update, to_remove):
        await cloud_prefs.async_update(
            alexa_enabled=False,
        )
        await hass.async_block_till_done()

    assert conf._alexa_sync_unsub is None
    assert to_update == []
    assert to_remove == [
        binary_sensor_entry.entity_id,
        sensor_entry.entity_id,
        light_entry.entity_id,
    ]


@pytest.mark.usefixtures("mock_cloud_login")
async def test_alexa_entity_registry_sync(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    cloud_prefs: CloudPreferences,
) -> None:
    """Test Alexa config responds to entity registry."""
    # Enable exposing new entities to Alexa
    expose_new(hass, True)

    await alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, hass.data[DATA_CLOUD]
    ).async_initialize()

    with patch_sync_helper() as (to_update, to_remove):
        entry = entity_registry.async_get_or_create(
            "light", "test", "unique", suggested_object_id="kitchen"
        )
        await hass.async_block_till_done()

    assert to_update == [entry.entity_id]
    assert to_remove == []

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "remove", "entity_id": entry.entity_id},
        )
        await hass.async_block_till_done()

    assert to_update == []
    assert to_remove == [entry.entity_id]

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {
                "action": "update",
                "entity_id": entry.entity_id,
                "changes": ["entity_id"],
                "old_entity_id": "light.living_room",
            },
        )
        await hass.async_block_till_done()

    assert to_update == [entry.entity_id]
    assert to_remove == ["light.living_room"]

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "update", "entity_id": entry.entity_id, "changes": ["icon"]},
        )
        await hass.async_block_till_done()

    assert to_update == []
    assert to_remove == []


async def test_alexa_update_report_state(
    hass: HomeAssistant, cloud_prefs: CloudPreferences, cloud_stub: Mock
) -> None:
    """Test Alexa config responds to reporting state."""
    assert await async_setup_component(hass, "homeassistant", {})
    await cloud_prefs.async_update(
        alexa_report_state=False,
    )
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )
    await conf.async_initialize()
    await conf.set_authorized(True)

    with (
        patch(
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig.async_sync_entities",
        ) as mock_sync,
        patch(
            "homeassistant.components.cloud.alexa_config.CloudAlexaConfig.async_enable_proactive_mode",
        ),
    ):
        await cloud_prefs.async_update(alexa_report_state=True)
        await hass.async_block_till_done()

    assert len(mock_sync.mock_calls) == 1


@pytest.mark.usefixtures("mock_expired_cloud_login")
def test_enabled_requires_valid_sub(
    hass: HomeAssistant, cloud_prefs: CloudPreferences
) -> None:
    """Test that alexa config enabled requires a valid Cloud sub."""
    assert cloud_prefs.alexa_enabled
    assert hass.data[DATA_CLOUD].is_logged_in
    assert hass.data[DATA_CLOUD].subscription_expired

    config = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, hass.data[DATA_CLOUD]
    )

    assert not config.enabled


async def test_alexa_handle_logout(
    hass: HomeAssistant, cloud_prefs: CloudPreferences, cloud_stub: Mock
) -> None:
    """Test Alexa config responds to logging out."""
    assert await async_setup_component(hass, "homeassistant", {})
    aconf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )

    await aconf.async_initialize()

    with patch(
        "homeassistant.components.alexa.config.async_enable_proactive_mode",
        return_value=Mock(),
    ) as mock_enable:
        await aconf.async_enable_proactive_mode()
        await hass.async_block_till_done()

    assert len(aconf._on_deinitialize) == 5

    # This will trigger a prefs update when we logout.
    await cloud_prefs.get_cloud_user()

    cloud_stub.is_logged_in = False
    with patch.object(
        cloud_stub.auth,
        "async_check_token",
        side_effect=AssertionError("Should not be called"),
    ):
        # Fake logging out; CloudClient.logout_cleanups sets username to None
        # and deinitializes the Google config.
        await cloud_prefs.async_set_username(None)
        aconf.async_deinitialize()
        await hass.async_block_till_done()
        # Check listeners are removed:
        assert not aconf._on_deinitialize

    assert len(mock_enable.return_value.mock_calls) == 1


@pytest.mark.parametrize("alexa_settings_version", [1, 2])
async def test_alexa_config_migrate_expose_entity_prefs(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    cloud_stub: Mock,
    entity_registry: er.EntityRegistry,
    alexa_settings_version: int,
) -> None:
    """Test migrating Alexa entity config."""
    hass.set_state(CoreState.starting)

    assert await async_setup_component(hass, "homeassistant", {})
    hass.states.async_set("light.state_only", "on")
    entity_exposed = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_exposed",
        suggested_object_id="exposed",
    )

    entity_migrated = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_migrated",
        suggested_object_id="migrated",
    )

    entity_config = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_config",
        suggested_object_id="config",
        entity_category=EntityCategory.CONFIG,
    )

    entity_default = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_default",
        suggested_object_id="default",
    )

    entity_blocked = entity_registry.async_get_or_create(
        "group",
        "test",
        "group_all_locks",
        suggested_object_id="all_locks",
    )
    assert entity_blocked.entity_id == "group.all_locks"

    await cloud_prefs.async_update(
        alexa_enabled=True,
        alexa_report_state=False,
        alexa_settings_version=alexa_settings_version,
    )
    expose_entity(hass, entity_migrated.entity_id, False)

    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS]["light.unknown"] = {
        PREF_SHOULD_EXPOSE: True
    }
    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS]["light.state_only"] = {
        PREF_SHOULD_EXPOSE: False
    }
    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS][entity_exposed.entity_id] = {
        PREF_SHOULD_EXPOSE: True
    }
    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS][entity_migrated.entity_id] = {
        PREF_SHOULD_EXPOSE: True
    }
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )
    await conf.async_initialize()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert async_get_entity_settings(hass, "light.unknown") == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, "light.state_only") == {
        "cloud.alexa": {"should_expose": False}
    }
    assert async_get_entity_settings(hass, entity_exposed.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, entity_migrated.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, entity_config.entity_id) == {
        "cloud.alexa": {"should_expose": False}
    }
    assert async_get_entity_settings(hass, entity_default.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, entity_blocked.entity_id) == {
        "cloud.alexa": {"should_expose": False}
    }


async def test_alexa_config_migrate_expose_entity_prefs_v2_no_exposed(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrating Alexa entity config from v2 to v3 when no entity is exposed."""
    hass.set_state(CoreState.starting)

    assert await async_setup_component(hass, "homeassistant", {})
    hass.states.async_set("light.state_only", "on")
    entity_migrated = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_migrated",
        suggested_object_id="migrated",
    )
    await cloud_prefs.async_update(
        alexa_enabled=True,
        alexa_report_state=False,
        alexa_settings_version=2,
    )
    expose_entity(hass, "light.state_only", False)
    expose_entity(hass, entity_migrated.entity_id, False)

    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS]["light.state_only"] = {
        PREF_SHOULD_EXPOSE: True
    }
    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS][entity_migrated.entity_id] = {
        PREF_SHOULD_EXPOSE: True
    }
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, Mock(is_logged_in=False)
    )
    await conf.async_initialize()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert async_get_entity_settings(hass, "light.state_only") == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, entity_migrated.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }


async def test_alexa_config_migrate_expose_entity_prefs_v2_exposed(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrating Alexa entity config from v2 to v3 when an entity is exposed."""
    hass.set_state(CoreState.starting)

    assert await async_setup_component(hass, "homeassistant", {})
    hass.states.async_set("light.state_only", "on")
    entity_migrated = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_migrated",
        suggested_object_id="migrated",
    )
    await cloud_prefs.async_update(
        alexa_enabled=True,
        alexa_report_state=False,
        alexa_settings_version=2,
    )
    expose_entity(hass, "light.state_only", False)
    expose_entity(hass, entity_migrated.entity_id, True)

    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS]["light.state_only"] = {
        PREF_SHOULD_EXPOSE: True
    }
    cloud_prefs._prefs[PREF_ALEXA_ENTITY_CONFIGS][entity_migrated.entity_id] = {
        PREF_SHOULD_EXPOSE: True
    }
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, Mock(is_logged_in=False)
    )
    await conf.async_initialize()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert async_get_entity_settings(hass, "light.state_only") == {
        "cloud.alexa": {"should_expose": False}
    }
    assert async_get_entity_settings(hass, entity_migrated.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }


async def test_alexa_config_migrate_expose_entity_prefs_default_none(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    cloud_stub: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrating Alexa entity config."""
    hass.set_state(CoreState.starting)

    assert await async_setup_component(hass, "homeassistant", {})
    entity_default = entity_registry.async_get_or_create(
        "light",
        "test",
        "light_default",
        suggested_object_id="default",
    )

    await cloud_prefs.async_update(
        alexa_enabled=True,
        alexa_report_state=False,
        alexa_settings_version=1,
    )

    cloud_prefs._prefs[PREF_ALEXA_DEFAULT_EXPOSE] = None
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )
    await conf.async_initialize()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert async_get_entity_settings(hass, entity_default.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }


async def test_alexa_config_migrate_expose_entity_prefs_default(
    hass: HomeAssistant,
    cloud_prefs: CloudPreferences,
    cloud_stub: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrating Alexa entity config."""
    hass.set_state(CoreState.starting)

    assert await async_setup_component(hass, "homeassistant", {})

    binary_sensor_supported = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "binary_sensor_supported",
        original_device_class="door",
        suggested_object_id="supported",
    )

    binary_sensor_unsupported = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "binary_sensor_unsupported",
        original_device_class="battery",
        suggested_object_id="unsupported",
    )

    light = entity_registry.async_get_or_create(
        "light",
        "test",
        "unique",
        suggested_object_id="light",
    )

    sensor_supported = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "sensor_supported",
        original_device_class="temperature",
        suggested_object_id="supported",
    )

    sensor_unsupported = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "sensor_unsupported",
        original_device_class="battery",
        suggested_object_id="unsupported",
    )

    water_heater = entity_registry.async_get_or_create(
        "water_heater",
        "test",
        "unique",
        suggested_object_id="water_heater",
    )

    await cloud_prefs.async_update(
        alexa_enabled=True,
        alexa_report_state=False,
        alexa_settings_version=1,
    )

    cloud_prefs._prefs[PREF_ALEXA_DEFAULT_EXPOSE] = [
        "binary_sensor",
        "light",
        "sensor",
        "water_heater",
    ]
    conf = alexa_config.CloudAlexaConfig(
        hass, ALEXA_SCHEMA({}), "mock-user-id", cloud_prefs, cloud_stub
    )
    await conf.async_initialize()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert async_get_entity_settings(hass, binary_sensor_supported.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, binary_sensor_unsupported.entity_id) == {
        "cloud.alexa": {"should_expose": False}
    }
    assert async_get_entity_settings(hass, light.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, sensor_supported.entity_id) == {
        "cloud.alexa": {"should_expose": True}
    }
    assert async_get_entity_settings(hass, sensor_unsupported.entity_id) == {
        "cloud.alexa": {"should_expose": False}
    }
    assert async_get_entity_settings(hass, water_heater.entity_id) == {
        "cloud.alexa": {"should_expose": False}
    }
