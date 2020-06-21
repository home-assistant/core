"""Test Customize config panel."""
import json

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.config import DATA_CUSTOMIZE

from tests.async_mock import patch


async def test_get_entity(hass, hass_client):
    """Test getting entity."""
    with patch.object(config, "SECTIONS", ["customize"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    def mock_read(path):
        """Mock reading data."""
        return {"hello.beer": {"free": "beer"}, "other.entity": {"do": "something"}}

    hass.data[DATA_CUSTOMIZE] = {"hello.beer": {"cold": "beer"}}
    with patch("homeassistant.components.config._read", mock_read):
        resp = await client.get("/api/config/customize/config/hello.beer")

    assert resp.status == 200
    result = await resp.json()

    assert result == {"local": {"free": "beer"}, "global": {"cold": "beer"}}


async def test_update_entity(hass, hass_client):
    """Test updating entity."""
    with patch.object(config, "SECTIONS", ["customize"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    orig_data = {
        "hello.beer": {"ignored": True},
        "other.entity": {"polling_intensity": 2},
    }

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    hass.states.async_set("hello.world", "state", {"a": "b"})
    with patch("homeassistant.components.config._read", mock_read), patch(
        "homeassistant.components.config._write", mock_write
    ), patch(
        "homeassistant.config.async_hass_config_yaml", return_value={},
    ):
        resp = await client.post(
            "/api/config/customize/config/hello.world",
            data=json.dumps(
                {"name": "Beer", "entities": ["light.top", "light.bottom"]}
            ),
        )
        await hass.async_block_till_done()

    assert resp.status == 200
    result = await resp.json()
    assert result == {"result": "ok"}

    state = hass.states.get("hello.world")
    assert state.state == "state"
    assert dict(state.attributes) == {
        "a": "b",
        "name": "Beer",
        "entities": ["light.top", "light.bottom"],
    }

    orig_data["hello.world"]["name"] = "Beer"
    orig_data["hello.world"]["entities"] = ["light.top", "light.bottom"]

    assert written[0] == orig_data


async def test_update_entity_invalid_key(hass, hass_client):
    """Test updating entity."""
    with patch.object(config, "SECTIONS", ["customize"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    resp = await client.post(
        "/api/config/customize/config/not_entity", data=json.dumps({"name": "YO"})
    )

    assert resp.status == 400


async def test_update_entity_invalid_json(hass, hass_client):
    """Test updating entity."""
    with patch.object(config, "SECTIONS", ["customize"]):
        await async_setup_component(hass, "config", {})

    client = await hass_client()

    resp = await client.post("/api/config/customize/config/hello.beer", data="not json")

    assert resp.status == 400
