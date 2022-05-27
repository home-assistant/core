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
async def test_delete_script(hass, hass_client):
    """Test deleting a script."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 2

    client = await hass_client()

    orig_data = {"one": {}, "two": {}}

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ):
        resp = await client.delete("/api/config/script/config/two")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert len(written) == 1
    assert written[0] == {"one": {}}

    assert len(ent_reg.entities) == 1
