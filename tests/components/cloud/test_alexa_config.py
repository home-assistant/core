"""Test Alexa config."""
import contextlib
from unittest.mock import patch

from homeassistant.components.cloud import ALEXA_SCHEMA, alexa_config
from homeassistant.util.dt import utcnow
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from tests.common import mock_coro, async_fire_time_changed


async def test_alexa_config_expose_entity_prefs(hass, cloud_prefs):
    """Test Alexa config should expose using prefs."""
    entity_conf = {"should_expose": False}
    await cloud_prefs.async_update(alexa_entity_configs={"light.kitchen": entity_conf})
    conf = alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    assert not conf.should_expose("light.kitchen")
    entity_conf["should_expose"] = True
    assert conf.should_expose("light.kitchen")


async def test_alexa_config_report_state(hass, cloud_prefs):
    """Test Alexa config should expose using prefs."""
    conf = alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    assert cloud_prefs.alexa_report_state is False
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False

    with patch.object(conf, "async_get_access_token", return_value=mock_coro("hello")):
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


@contextlib.contextmanager
def patch_sync_helper():
    """Patch sync helper.

    In Py3.7 this would have been an async context manager.
    """
    to_update = []
    to_remove = []

    with patch("homeassistant.components.cloud.alexa_config.SYNC_DELAY", 0), patch(
        "homeassistant.components.cloud.alexa_config.AlexaConfig._sync_helper",
        side_effect=mock_coro,
    ) as mock_helper:
        yield to_update, to_remove

    actual_to_update, actual_to_remove = mock_helper.mock_calls[0][1]
    to_update.extend(actual_to_update)
    to_remove.extend(actual_to_remove)


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
            {"action": "update", "entity_id": "light.kitchen"},
        )
        await hass.async_block_till_done()

    assert to_update == []
    assert to_remove == []


async def test_alexa_update_report_state(hass, cloud_prefs):
    """Test Alexa config responds to reporting state."""
    alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    with patch(
        "homeassistant.components.cloud.alexa_config.AlexaConfig."
        "async_sync_entities",
        side_effect=mock_coro,
    ) as mock_sync, patch(
        "homeassistant.components.cloud.alexa_config."
        "AlexaConfig.async_enable_proactive_mode",
        side_effect=mock_coro,
    ):
        await cloud_prefs.async_update(alexa_report_state=True)
        await hass.async_block_till_done()

    assert len(mock_sync.mock_calls) == 1
