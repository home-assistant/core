"""Tests for config/script."""
from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.helpers import entity_registry as er

from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture(autouse=True)
async def setup_script(hass, script_config, stub_blueprint_populate):  # noqa: F811
    """Set up script integration."""
    assert await async_setup_component(hass, "script", {"script": script_config})


@pytest.mark.parametrize(
    "script_config",
    (
        {
            "one": {"alias": "Light on", "sequence": []},
            "two": {"alias": "Light off", "sequence": []},
        },
    ),
)
async def test_delete_script(hass, hass_client, hass_config_store):
    """Test deleting a script."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.one",
        "script.two",
    ]

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 2

    client = await hass_client()

    orig_data = {"one": {}, "two": {}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.delete("/api/config/script/config/two")
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.one",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["scripts.yaml"] == {"one": {}}

    assert len(ent_reg.entities) == 1
