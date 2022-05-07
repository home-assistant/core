"""Test the Cloud Google Config."""
from http import HTTPStatus
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.cloud import GACTIONS_SCHEMA
from homeassistant.components.cloud.google_config import CloudGoogleConfig
from homeassistant.components.google_assistant import helpers as ga_helpers
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed, mock_registry


@pytest.fixture
def mock_conf(hass, cloud_prefs):
    """Mock Google conf."""
    return CloudGoogleConfig(
        hass,
        GACTIONS_SCHEMA({}),
        "mock-user-id",
        cloud_prefs,
        Mock(claims={"cognito:username": "abcdefghjkl"}),
    )


async def test_google_update_report_state(mock_conf, hass, cloud_prefs):
    """Test Google config responds to updating preference."""
    await mock_conf.async_initialize()
    await mock_conf.async_connect_agent_user("mock-user-id")

    mock_conf._cloud.subscription_expired = False

    with patch.object(mock_conf, "async_sync_entities") as mock_sync, patch(
        "homeassistant.components.google_assistant.report_state.async_enable_report_state"
    ) as mock_report_state:
        await cloud_prefs.async_update(google_report_state=True)
        await hass.async_block_till_done()

    assert len(mock_sync.mock_calls) == 1
    assert len(mock_report_state.mock_calls) == 1


async def test_google_update_report_state_subscription_expired(
    mock_conf, hass, cloud_prefs
):
    """Test Google config not reporting state when subscription has expired."""
    await mock_conf.async_initialize()
    await mock_conf.async_connect_agent_user("mock-user-id")

    assert mock_conf._cloud.subscription_expired

    with patch.object(mock_conf, "async_sync_entities") as mock_sync, patch(
        "homeassistant.components.google_assistant.report_state.async_enable_report_state"
    ) as mock_report_state:
        await cloud_prefs.async_update(google_report_state=True)
        await hass.async_block_till_done()

    assert len(mock_sync.mock_calls) == 0
    assert len(mock_report_state.mock_calls) == 0


async def test_sync_entities(mock_conf, hass, cloud_prefs):
    """Test sync devices."""
    await mock_conf.async_initialize()
    await mock_conf.async_connect_agent_user("mock-user-id")

    assert len(mock_conf._store.agent_user_ids) == 1

    with patch(
        "hass_nabucasa.cloud_api.async_google_actions_request_sync",
        return_value=Mock(status=HTTPStatus.NOT_FOUND),
    ) as mock_request_sync:
        assert (
            await mock_conf.async_sync_entities("mock-user-id") == HTTPStatus.NOT_FOUND
        )
        assert len(mock_conf._store.agent_user_ids) == 0
        assert len(mock_request_sync.mock_calls) == 1


async def test_google_update_expose_trigger_sync(hass, cloud_prefs):
    """Test Google config responds to updating exposed entities."""
    with freeze_time(utcnow()):
        config = CloudGoogleConfig(
            hass,
            GACTIONS_SCHEMA({}),
            "mock-user-id",
            cloud_prefs,
            Mock(claims={"cognito:username": "abcdefghjkl"}),
        )
        await config.async_initialize()
        await config.async_connect_agent_user("mock-user-id")

        with patch.object(config, "async_sync_entities") as mock_sync, patch.object(
            ga_helpers, "SYNC_DELAY", 0
        ):
            await cloud_prefs.async_update_google_entity_config(
                entity_id="light.kitchen", should_expose=True
            )
            await hass.async_block_till_done()
            async_fire_time_changed(hass, utcnow())
            await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 1

        with patch.object(config, "async_sync_entities") as mock_sync, patch.object(
            ga_helpers, "SYNC_DELAY", 0
        ):
            await cloud_prefs.async_update_google_entity_config(
                entity_id="light.kitchen", should_expose=False
            )
            await cloud_prefs.async_update_google_entity_config(
                entity_id="binary_sensor.door", should_expose=True
            )
            await cloud_prefs.async_update_google_entity_config(
                entity_id="sensor.temp", should_expose=True
            )
            await hass.async_block_till_done()
            async_fire_time_changed(hass, utcnow())
            await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 1


async def test_google_entity_registry_sync(hass, mock_cloud_login, cloud_prefs):
    """Test Google config responds to entity registry."""
    config = CloudGoogleConfig(
        hass, GACTIONS_SCHEMA({}), "mock-user-id", cloud_prefs, hass.data["cloud"]
    )
    await config.async_initialize()
    await config.async_connect_agent_user("mock-user-id")

    with patch.object(
        config, "async_schedule_google_sync_all"
    ) as mock_sync, patch.object(config, "async_sync_entities_all"), patch.object(
        ga_helpers, "SYNC_DELAY", 0
    ):
        # Created entity
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "create", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 1

        # Removed entity
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "remove", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 2

        # Entity registry updated with relevant changes
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {
                "action": "update",
                "entity_id": "light.kitchen",
                "changes": ["entity_id"],
            },
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 3

        # Entity registry updated with non-relevant changes
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "update", "entity_id": "light.kitchen", "changes": ["icon"]},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 3

        # When hass is not started yet we wait till started
        hass.state = CoreState.starting
        hass.bus.async_fire(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "create", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 3


async def test_google_device_registry_sync(hass, mock_cloud_login, cloud_prefs):
    """Test Google config responds to device registry."""
    config = CloudGoogleConfig(
        hass, GACTIONS_SCHEMA({}), "mock-user-id", cloud_prefs, hass.data["cloud"]
    )
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get_or_create(
        "light", "hue", "1234", device_id="1234", area_id="ABCD"
    )

    with patch.object(config, "async_sync_entities_all"):
        await config.async_initialize()
        await hass.async_block_till_done()
    await config.async_connect_agent_user("mock-user-id")

    with patch.object(config, "async_schedule_google_sync_all") as mock_sync:
        # Device registry updated with non-relevant changes
        hass.bus.async_fire(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            {
                "action": "update",
                "device_id": "1234",
                "changes": ["manufacturer"],
            },
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 0

        # Device registry updated with relevant changes
        # but entity has area ID so not impacted
        hass.bus.async_fire(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            {
                "action": "update",
                "device_id": "1234",
                "changes": ["area_id"],
            },
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 0

        ent_reg.async_update_entity(entity_entry.entity_id, area_id=None)

        # Device registry updated with relevant changes
        # but entity has area ID so not impacted
        hass.bus.async_fire(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            {
                "action": "update",
                "device_id": "1234",
                "changes": ["area_id"],
            },
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 1


async def test_sync_google_when_started(hass, mock_cloud_login, cloud_prefs):
    """Test Google config syncs on init."""
    config = CloudGoogleConfig(
        hass, GACTIONS_SCHEMA({}), "mock-user-id", cloud_prefs, hass.data["cloud"]
    )
    with patch.object(config, "async_sync_entities_all") as mock_sync:
        await config.async_initialize()
        await config.async_connect_agent_user("mock-user-id")
        await hass.async_block_till_done()
        assert len(mock_sync.mock_calls) == 1


async def test_sync_google_on_home_assistant_start(hass, mock_cloud_login, cloud_prefs):
    """Test Google config syncs when home assistant started."""
    config = CloudGoogleConfig(
        hass, GACTIONS_SCHEMA({}), "mock-user-id", cloud_prefs, hass.data["cloud"]
    )
    hass.state = CoreState.starting
    with patch.object(config, "async_sync_entities_all") as mock_sync:
        await config.async_initialize()
        await config.async_connect_agent_user("mock-user-id")
        assert len(mock_sync.mock_calls) == 0

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(mock_sync.mock_calls) == 1


async def test_google_config_expose_entity_prefs(hass, mock_conf, cloud_prefs):
    """Test Google config should expose using prefs."""
    entity_registry = mock_registry(hass)

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

    entity_conf = {"should_expose": False}
    await cloud_prefs.async_update(
        google_entity_configs={"light.kitchen": entity_conf},
        google_default_expose=["light"],
    )

    state = State("light.kitchen", "on")
    state_config = State(entity_entry1.entity_id, "on")
    state_diagnostic = State(entity_entry2.entity_id, "on")
    state_hidden_integration = State(entity_entry3.entity_id, "on")
    state_hidden_user = State(entity_entry4.entity_id, "on")

    assert not mock_conf.should_expose(state)
    assert not mock_conf.should_expose(state_config)
    assert not mock_conf.should_expose(state_diagnostic)
    assert not mock_conf.should_expose(state_hidden_integration)
    assert not mock_conf.should_expose(state_hidden_user)

    entity_conf["should_expose"] = True
    assert mock_conf.should_expose(state)
    # categorized and hidden entities should not be exposed
    assert not mock_conf.should_expose(state_config)
    assert not mock_conf.should_expose(state_diagnostic)
    assert not mock_conf.should_expose(state_hidden_integration)
    assert not mock_conf.should_expose(state_hidden_user)

    entity_conf["should_expose"] = None
    assert mock_conf.should_expose(state)
    # categorized and hidden entities should not be exposed
    assert not mock_conf.should_expose(state_config)
    assert not mock_conf.should_expose(state_diagnostic)
    assert not mock_conf.should_expose(state_hidden_integration)
    assert not mock_conf.should_expose(state_hidden_user)

    await cloud_prefs.async_update(
        google_default_expose=["sensor"],
    )
    assert not mock_conf.should_expose(state)


def test_enabled_requires_valid_sub(hass, mock_expired_cloud_login, cloud_prefs):
    """Test that google config enabled requires a valid Cloud sub."""
    assert cloud_prefs.google_enabled
    assert hass.data["cloud"].is_logged_in
    assert hass.data["cloud"].subscription_expired

    config = CloudGoogleConfig(
        hass, GACTIONS_SCHEMA({}), "mock-user-id", cloud_prefs, hass.data["cloud"]
    )

    assert not config.enabled


async def test_setup_integration(hass, mock_conf, cloud_prefs):
    """Test that we set up the integration if used."""
    mock_conf._cloud.subscription_expired = False

    assert "google_assistant" not in hass.config.components

    await mock_conf.async_initialize()
    await hass.async_block_till_done()
    assert "google_assistant" in hass.config.components

    hass.config.components.remove("google_assistant")

    await cloud_prefs.async_update()
    await hass.async_block_till_done()
    assert "google_assistant" in hass.config.components


async def test_google_handle_logout(hass, cloud_prefs, mock_cloud_login):
    """Test Google config responds to logging out."""
    gconf = CloudGoogleConfig(
        hass, GACTIONS_SCHEMA({}), "mock-user-id", cloud_prefs, Mock(is_logged_in=False)
    )

    await gconf.async_initialize()

    with patch(
        "homeassistant.components.google_assistant.report_state.async_enable_report_state",
    ) as mock_enable:
        gconf.async_enable_report_state()

    assert len(mock_enable.mock_calls) == 1

    # This will trigger a prefs update when we logout.
    await cloud_prefs.get_cloud_user()

    with patch.object(
        hass.data["cloud"].auth,
        "async_check_token",
        side_effect=AssertionError("Should not be called"),
    ):
        await cloud_prefs.async_set_username(None)
        await hass.async_block_till_done()

    assert len(mock_enable.return_value.mock_calls) == 1
