"""The tests for the apprise notification platform."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component

BASE_COMPONENT = "notify"


async def test_apprise_config_load_fail(hass):
    """Test apprise configuration failures."""

    config = {
        BASE_COMPONENT: {"name": "test", "platform": "apprise", "config": "/path/"}
    }

    with patch("apprise.AppriseConfig.add", return_value=False):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

    with patch("apprise.AppriseConfig.add", return_value=True):
        with patch("apprise.Apprise.add", return_value=False):
            assert await async_setup_component(hass, BASE_COMPONENT, config)
            await hass.async_block_till_done()


async def test_apprise_config_load_okay(hass, tmp_path):
    """Test apprise configuration failures."""

    # Test cases where our URL is invalid
    d = tmp_path / "apprise-config"
    d.mkdir()
    f = d / "apprise"
    f.write_text("mailto://user:pass@example.com/")

    config = {BASE_COMPONENT: {"name": "test", "platform": "apprise", "config": str(f)}}

    assert await async_setup_component(hass, BASE_COMPONENT, config)
    await hass.async_block_till_done()


async def test_apprise_url_load_fail(hass):
    """Test apprise url failure."""

    config = {
        BASE_COMPONENT: {
            "name": "test",
            "platform": "apprise",
            "url": "mailto://user:pass@example.com",
        }
    }
    with patch("apprise.Apprise.add", return_value=False):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()


async def test_apprise_notification(hass):
    """Test apprise notification."""

    config = {
        BASE_COMPONENT: {
            "name": "test",
            "platform": "apprise",
            "url": "mailto://user:pass@example.com",
        }
    }

    # Our Message
    data = {"title": "Test Title", "message": "Test Message"}

    with patch("apprise.Apprise") as mock_apprise:
        mock_apprise.notify.return_value = True
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test the call to our underlining notify() call
        await hass.services.async_call(BASE_COMPONENT, "test", data)
        await hass.async_block_till_done()
