"""Tests for config/script."""
from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config

from tests.async_mock import patch


async def test_delete_script(hass, hass_client):
    """Test deleting a script."""
    with patch.object(config, "SECTIONS", ["script"]):
        await async_setup_component(hass, "config", {})

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

    assert resp.status == 200
    result = await resp.json()
    assert result == {"result": "ok"}

    assert len(written) == 1
    assert written[0] == {"one": {}}
