"""The tests for the apprise notification platform."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

BASE_COMPONENT = "notify"


@pytest.fixture(autouse=True)
def reset_log_level():
    """Set and reset log level after each test case."""
    logger = logging.getLogger("apprise")
    orig_level = logger.level
    logger.setLevel(logging.DEBUG)
    yield
    logger.setLevel(orig_level)


async def test_apprise_config_load_fail01(hass: HomeAssistant) -> None:
    """Test apprise configuration failures 1."""

    config = {
        BASE_COMPONENT: {"name": "test", "platform": "apprise", "config": "/path/"}
    }

    with patch(
        "homeassistant.components.apprise.notify.apprise.AppriseConfig.add",
        return_value=False,
    ):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test that our service failed to load
        assert not hass.services.has_service(BASE_COMPONENT, "test")


async def test_apprise_config_load_fail02(hass: HomeAssistant) -> None:
    """Test apprise configuration failures 2."""

    config = {
        BASE_COMPONENT: {"name": "test", "platform": "apprise", "config": "/path/"}
    }

    with (
        patch(
            "homeassistant.components.apprise.notify.apprise.Apprise.add",
            return_value=False,
        ),
        patch(
            "homeassistant.components.apprise.notify.apprise.AppriseConfig.add",
            return_value=True,
        ),
    ):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test that our service failed to load
        assert not hass.services.has_service(BASE_COMPONENT, "test")


async def test_apprise_config_load_okay(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test apprise configuration failures."""

    # Test cases where our URL is invalid
    d = tmp_path / "apprise-config"
    d.mkdir()
    f = d / "apprise"
    f.write_text("mailto://user:pass@example.com/")

    config = {BASE_COMPONENT: {"name": "test", "platform": "apprise", "config": str(f)}}

    assert await async_setup_component(hass, BASE_COMPONENT, config)
    await hass.async_block_till_done()

    # Valid configuration was loaded; our service is good
    assert hass.services.has_service(BASE_COMPONENT, "test")


async def test_apprise_url_load_fail(hass: HomeAssistant) -> None:
    """Test apprise url failure."""

    config = {
        BASE_COMPONENT: {
            "name": "test",
            "platform": "apprise",
            "url": "mailto://user:pass@example.com",
        }
    }
    with patch(
        "homeassistant.components.apprise.notify.apprise.Apprise.add",
        return_value=False,
    ):
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test that our service failed to load
        assert not hass.services.has_service(BASE_COMPONENT, "test")


async def test_apprise_notification(hass: HomeAssistant) -> None:
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

    with patch(
        "homeassistant.components.apprise.notify.apprise.Apprise"
    ) as mock_apprise:
        obj = MagicMock()
        obj.add.return_value = True
        obj.notify.return_value = True
        mock_apprise.return_value = obj
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test the existence of our service
        assert hass.services.has_service(BASE_COMPONENT, "test")

        # Test the call to our underlining notify() call
        await hass.services.async_call(BASE_COMPONENT, "test", data)
        await hass.async_block_till_done()

        # Validate calls were made under the hood correctly
        obj.add.assert_called_once_with(config[BASE_COMPONENT]["url"])
        obj.notify.assert_called_once_with(
            body=data["message"], title=data["title"], tag=None
        )


async def test_apprise_multiple_notification(hass: HomeAssistant) -> None:
    """Test apprise notification."""

    config = {
        BASE_COMPONENT: {
            "name": "test",
            "platform": "apprise",
            "url": [
                "mailto://user:pass@example.com, mailto://user:pass@gmail.com",
                "json://user:pass@gmail.com",
            ],
        }
    }

    # Our Message
    data = {"title": "Test Title", "message": "Test Message"}

    with patch(
        "homeassistant.components.apprise.notify.apprise.Apprise"
    ) as mock_apprise:
        obj = MagicMock()
        obj.add.return_value = True
        obj.notify.return_value = True
        mock_apprise.return_value = obj
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test the existence of our service
        assert hass.services.has_service(BASE_COMPONENT, "test")

        # Test the call to our underlining notify() call
        await hass.services.async_call(BASE_COMPONENT, "test", data)
        await hass.async_block_till_done()

        # Validate 2 calls were made under the hood
        assert obj.add.call_count == 2
        obj.notify.assert_called_once_with(
            body=data["message"], title=data["title"], tag=None
        )


async def test_apprise_notification_with_target(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test apprise notification with a target."""

    # Test cases where our URL is invalid
    d = tmp_path / "apprise-config"
    d.mkdir()
    f = d / "apprise"

    # Write 2 config entries each assigned to different tags
    f.write_text("devops=mailto://user:pass@example.com/\r\n")
    f.write_text("system,alert=syslog://\r\n")

    config = {BASE_COMPONENT: {"name": "test", "platform": "apprise", "config": str(f)}}

    # Our Message, only notify the services tagged with "devops"
    data = {"title": "Test Title", "message": "Test Message", "target": ["devops"]}

    with patch(
        "homeassistant.components.apprise.notify.apprise.Apprise"
    ) as mock_apprise:
        apprise_obj = MagicMock()
        apprise_obj.add.return_value = True
        apprise_obj.notify.return_value = True
        mock_apprise.return_value = apprise_obj
        assert await async_setup_component(hass, BASE_COMPONENT, config)
        await hass.async_block_till_done()

        # Test the existence of our service
        assert hass.services.has_service(BASE_COMPONENT, "test")

        # Test the call to our underlining notify() call
        await hass.services.async_call(BASE_COMPONENT, "test", data)
        await hass.async_block_till_done()

        # Validate calls were made under the hood correctly
        apprise_obj.notify.assert_called_once_with(
            body=data["message"], title=data["title"], tag=data["target"]
        )
