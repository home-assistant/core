"""Test Alexa config."""
import contextlib
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.cloud import ALEXA_SCHEMA, alexa_config
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


async def test_alexa_config_expose_entity_prefs(hass, cloud_prefs):
    """Test Alexa config should expose using prefs."""
    entity_conf = {"should_expose": False}
    await cloud_prefs.async_update(
        alexa_entity_configs={"light.kitchen": entity_conf},
        alexa_default_expose=["light"],
    )
    conf = alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    assert not conf.should_expose("light.kitchen")
    entity_conf["should_expose"] = True
    assert conf.should_expose("light.kitchen")

    entity_conf["should_expose"] = None
    assert conf.should_expose("light.kitchen")

    await cloud_prefs.async_update(
        alexa_default_expose=["sensor"],
    )
    assert not conf.should_expose("light.kitchen")


async def test_alexa_config_report_state(hass, cloud_prefs):
    """Test Alexa config should expose using prefs."""
    conf = alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

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


async def test_alexa_config_invalidate_token(hass, cloud_prefs, aioclient_mock):
    """Test Alexa config should expose using prefs."""
    aioclient_mock.post(
        "http://example/alexa_token",
        json={
            "access_token": "mock-token",
            "event_endpoint": "http://example.com/alexa_endpoint",
            "expires_in": 30,
        },
    )
    conf = alexa_config.AlexaConfig(
        hass,
        ALEXA_SCHEMA({}),
        cloud_prefs,
        Mock(
            alexa_access_token_url="http://example/alexa_token",
            auth=Mock(async_check_token=AsyncMock()),
            websession=hass.helpers.aiohttp_client.async_get_clientsession(),
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


@contextlib.contextmanager
def patch_sync_helper():
    """Patch sync helper.

    In Py3.7 this would have been an async context manager.
    """
    to_update = []
    to_remove = []

    def sync_helper(to_upd, to_rem):
        to_update.extend([ent_id for ent_id in to_upd if ent_id not in to_update])
        to_remove.extend([ent_id for ent_id in to_rem if ent_id not in to_remove])
        return True

    with patch("homeassistant.components.cloud.alexa_config.SYNC_DELAY", 0), patch(
        "homeassistant.components.cloud.alexa_config.AlexaConfig._sync_helper",
        side_effect=sync_helper,
    ):
        yield to_update, to_remove


async def test_alexa_update_expose_trigger_sync(hass, cloud_prefs):
    """Test Alexa config responds to updating exposed entities."""
    alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    with patch_sync_helper() as (to_update, to_remove):
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id="light.kitchen", should_expose=True
        )
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

    assert to_update == ["light.kitchen"]
    assert to_remove == []

    with patch_sync_helper() as (to_update, to_remove):
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id="light.kitchen", should_expose=False
        )
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id="binary_sensor.door", should_expose=True
        )
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id="sensor.temp", should_expose=True
        )
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

    assert sorted(to_update) == ["binary_sensor.door", "sensor.temp"]
    assert to_remove == ["light.kitchen"]


async def test_alexa_entity_registry_sync(hass, mock_cloud_login, cloud_prefs):
    """Test Alexa config responds to entity registry."""
    alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, hass.data["cloud"])

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "create", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

    assert to_update == ["light.kitchen"]
    assert to_remove == []

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "remove", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

    assert to_update == []
    assert to_remove == ["light.kitchen"]

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {
                "action": "update",
                "entity_id": "light.kitchen",
                "changes": ["entity_id"],
                "old_entity_id": "light.living_room",
            },
        )
        await hass.async_block_till_done()

    assert to_update == ["light.kitchen"]
    assert to_remove == ["light.living_room"]

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED,
            {"action": "update", "entity_id": "light.kitchen", "changes": ["icon"]},
        )
        await hass.async_block_till_done()

    assert to_update == []
    assert to_remove == []


async def test_alexa_update_report_state(hass, cloud_prefs):
    """Test Alexa config responds to reporting state."""
    alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    with patch(
        "homeassistant.components.cloud.alexa_config.AlexaConfig.async_sync_entities",
    ) as mock_sync, patch(
        "homeassistant.components.cloud.alexa_config.AlexaConfig.async_enable_proactive_mode",
    ):
        await cloud_prefs.async_update(alexa_report_state=True)
        await hass.async_block_till_done()

    assert len(mock_sync.mock_calls) == 1
