"""Vera tests."""
from unittest.mock import MagicMock

from mock import patch
from requests.exceptions import RequestException

from homeassistant.components.vera import CONF_CONTROLLER
from homeassistant.components.vera.config_flow import VeraFlowHandler
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


async def test_aync_step_user_success(hass: HomeAssistant) -> None:
    """Test function."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        vera_controller_class_mock.return_value = controller

        handler = VeraFlowHandler()
        handler.hass = hass
        base_url = "http://127.0.0.1/"

        result = await handler.async_step_user()
        assert result.get("type") == RESULT_TYPE_FORM
        assert result.get("step_id") == "setup"

        result = await handler.async_step_user({CONF_CONTROLLER: base_url})
        assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert result.get("title") == base_url
        assert result.get("data") == {CONF_CONTROLLER: base_url}


async def test_async_step_user_alredy_setup(hass: HomeAssistant) -> None:
    """Test function."""
    handler = VeraFlowHandler()
    handler.hass = hass

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await handler.async_step_user()
        assert result.get("type") == RESULT_TYPE_ABORT
        assert result.get("reason") == "already_setup"


async def test_aync_step_import_success(hass: HomeAssistant) -> None:
    """Test function."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        vera_controller_class_mock.return_value = controller

        handler = VeraFlowHandler()
        handler.hass = hass
        base_url = "http://127.0.0.1/"

        result = await handler.async_step_import({CONF_CONTROLLER: base_url})

        assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert result.get("title") == base_url
        assert result.get("data") == {CONF_CONTROLLER: base_url}


async def test_async_step_import_alredy_setup(hass: HomeAssistant) -> None:
    """Test function."""
    handler = VeraFlowHandler()
    handler.hass = hass

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await handler.async_step_import({})
        assert result.get("type") == RESULT_TYPE_ABORT
        assert result.get("reason") == "already_setup"


async def test_async_step_finish_error(hass: HomeAssistant) -> None:
    """Test function."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock(side_effect=RequestException())
        vera_controller_class_mock.return_value = controller

        handler = VeraFlowHandler()
        handler.hass = hass
        handler.async_create_entry = MagicMock(
            side_effect=Exception("Should not have been called.")
        )

        result = await handler.async_step_finish({CONF_CONTROLLER: "http://127.0.0.1/"})

        assert result.get("type") == "abort"
        assert result.get("reason") == "cannot_connect"
        assert result.get("description_placeholders") == {
            "base_url": "http://127.0.0.1/"
        }
