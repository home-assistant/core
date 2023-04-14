"""Test Automation config panel."""
from http import HTTPStatus
import json
from unittest.mock import ANY, patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.typing import ClientSessionGenerator


@pytest.fixture
async def setup_scene(hass, scene_config):
    """Set up scene integration."""
    assert await async_setup_component(hass, "scene", {"scene": scene_config})


@pytest.mark.parametrize("scene_config", ({},))
async def test_create_scene(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_scene,
) -> None:
    """Test creating a scene."""
    with patch.object(config, "SECTIONS", ["scene"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("scene")) == []

    client = await hass_client()

    orig_data = {}
    hass_config_store["scenes.yaml"] = orig_data

    resp = await client.post(
        "/api/config/scene/config/light_off",
        data=json.dumps(
            {
                # "id": "light_off",  # The id should be added when writing
                "name": "Lights off",
                "entities": {"light.bedroom": {"state": "off"}},
            }
        ),
    )
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("scene")) == [
        "scene.lights_off",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["scenes.yaml"] == [
        {
            "id": "light_off",
            "name": "Lights off",
            "entities": {"light.bedroom": {"state": "off"}},
        }
    ]


@pytest.mark.parametrize("scene_config", ({},))
async def test_update_scene(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_scene,
) -> None:
    """Test updating a scene."""
    with patch.object(config, "SECTIONS", ["scene"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("scene")) == []

    client = await hass_client()

    orig_data = [{"id": "light_on"}, {"id": "light_off"}]
    hass_config_store["scenes.yaml"] = orig_data

    resp = await client.post(
        "/api/config/scene/config/light_off",
        data=json.dumps(
            {
                "id": "light_off",
                "name": "Lights off",
                "entities": {"light.bedroom": {"state": "off"}},
            }
        ),
    )
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("scene")) == [
        "scene.lights_off",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["scenes.yaml"] == [
        {"id": "light_on"},
        {
            "id": "light_off",
            "name": "Lights off",
            "entities": {"light.bedroom": {"state": "off"}},
        },
    ]


@pytest.mark.parametrize("scene_config", ({},))
async def test_bad_formatted_scene(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_scene,
) -> None:
    """Test that we handle scene without ID."""
    with patch.object(config, "SECTIONS", ["scene"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("scene")) == []

    client = await hass_client()

    orig_data = [
        {
            # No ID
            "entities": {"light.bedroom": "on"}
        },
        {"id": "light_off"},
    ]
    hass_config_store["scenes.yaml"] = orig_data

    resp = await client.post(
        "/api/config/scene/config/light_off",
        data=json.dumps(
            {
                "id": "light_off",
                "name": "Lights off",
                "entities": {"light.bedroom": {"state": "off"}},
            }
        ),
    )
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("scene")) == [
        "scene.lights_off",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    # Verify ID added to orig_data
    assert hass_config_store["scenes.yaml"] == [
        {
            "id": ANY,
            "entities": {"light.bedroom": "on"},
        },
        {
            "id": "light_off",
            "name": "Lights off",
            "entities": {"light.bedroom": {"state": "off"}},
        },
    ]


@pytest.mark.parametrize(
    "scene_config",
    (
        [
            {"id": "light_on", "name": "Light on", "entities": {}},
            {"id": "light_off", "name": "Light off", "entities": {}},
        ],
    ),
)
async def test_delete_scene(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    setup_scene,
) -> None:
    """Test deleting a scene."""
    ent_reg = er.async_get(hass)

    assert len(ent_reg.entities) == 2

    with patch.object(config, "SECTIONS", ["scene"]):
        assert await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("scene")) == [
        "scene.light_off",
        "scene.light_on",
    ]

    client = await hass_client()

    orig_data = [{"id": "light_on"}, {"id": "light_off"}]
    hass_config_store["scenes.yaml"] = orig_data

    resp = await client.delete("/api/config/scene/config/light_on")
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("scene")) == [
        "scene.light_off",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["scenes.yaml"] == [
        {"id": "light_off"},
    ]

    assert len(ent_reg.entities) == 1
