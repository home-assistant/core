"""Test the Cloud Google Config."""
from unittest.mock import Mock

from homeassistant.components.cloud import GACTIONS_SCHEMA
from homeassistant.components.cloud.google_config import CloudGoogleConfig
from homeassistant.components.google_assistant import helpers as ga_helpers
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, HTTP_NOT_FOUND
from homeassistant.core import CoreState
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.util.dt import utcnow

from tests.async_mock import AsyncMock, patch
from tests.common import async_fire_time_changed


async def test_google_update_report_state(hass, cloud_prefs):
    """Test Google config responds to updating preference."""
    config = CloudGoogleConfig(
        hass,
        GACTIONS_SCHEMA({}),
        "mock-user-id",
        cloud_prefs,
        Mock(claims={"cognito:username": "abcdefghjkl"}),
    )
    await config.async_initialize()
    await config.async_connect_agent_user("mock-user-id")

    with patch.object(config, "async_sync_entities") as mock_sync, patch(
        "homeassistant.components.google_assistant.report_state.async_enable_report_state"
    ) as mock_report_state:
        await cloud_prefs.async_update(google_report_state=True)
        await hass.async_block_till_done()

    assert len(mock_sync.mock_calls) == 1
    assert len(mock_report_state.mock_calls) == 1


async def test_sync_entities(aioclient_mock, hass, cloud_prefs):
    """Test sync devices."""
    config = CloudGoogleConfig(
        hass,
        GACTIONS_SCHEMA({}),
        "mock-user-id",
        cloud_prefs,
        Mock(auth=Mock(async_check_token=AsyncMock())),
    )

    with patch(
        "hass_nabucasa.cloud_api.async_google_actions_request_sync",
        return_value=Mock(status=HTTP_NOT_FOUND),
    ) as mock_request_sync:
        assert await config.async_sync_entities("user") == HTTP_NOT_FOUND
        assert len(mock_request_sync.mock_calls) == 1


async def test_google_update_expose_trigger_sync(hass, cloud_prefs):
    """Test Google config responds to updating exposed entities."""
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
    ) as mock_sync, patch.object(ga_helpers, "SYNC_DELAY", 0):
        # Created entity
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "create", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 1

        # Removed entity
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "remove", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 2

        # Entity registry updated with relevant changes
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
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
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "update", "entity_id": "light.kitchen", "changes": ["icon"]},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 3

        # When hass is not started yet we wait till started
        hass.state = CoreState.starting
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "create", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

        assert len(mock_sync.mock_calls) == 3

    with patch.object(config, "async_sync_entities_all") as mock_sync:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(mock_sync.mock_calls) == 1
