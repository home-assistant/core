"""Vera tests."""
from unittest.mock import MagicMock

from mock import patch
from requests.exceptions import RequestException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vera import CONF_CONTROLLER, DOMAIN
from homeassistant.components.vera.config_flow import VeraFlowHandler
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_aync_step_user_success(hass: HomeAssistant) -> None:
    """Test function."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        controller.serial_number = "serial_number_0"
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result.get("type") == RESULT_TYPE_FORM
        assert result.get("step_id") == config_entries.SOURCE_USER

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_CONTROLLER: "http://127.0.0.1:123/"},
        )
        assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert result.get("title") == "http://127.0.0.1:123"
        assert result.get("data") == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
        }
        assert result.get("result").unique_id == controller.serial_number


async def test_async_step_user_already_setup(hass: HomeAssistant) -> None:
    """Test function."""
    handler = VeraFlowHandler()
    handler.context = {}
    handler.hass = hass

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result.get("type") == RESULT_TYPE_ABORT
        assert result.get("reason") == "already_setup"


async def test_aync_step_import_success(hass: HomeAssistant) -> None:
    """Test function."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        controller.serial_number = "serial_number_1"
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_CONTROLLER: "http://127.0.0.1:123/"},
        )

        assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert result.get("title") == "http://127.0.0.1:123"
        assert result.get("data") == {CONF_CONTROLLER: "http://127.0.0.1:123"}
        assert result.get("result").unique_id == controller.serial_number


async def test_async_step_import_alredy_setup(hass: HomeAssistant) -> None:
    """Test function."""
    handler = VeraFlowHandler()
    handler.context = {}
    handler.hass = hass

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
        )
        assert result.get("type") == RESULT_TYPE_ABORT
        assert result.get("reason") == "already_setup"


async def test_async_step_finish_error(hass: HomeAssistant) -> None:
    """Test function."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock(side_effect=RequestException())
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_CONTROLLER: "http://127.0.0.1:123/"},
        )

        assert result.get("type") == "abort"
        assert result.get("reason") == "cannot_connect"
        assert result.get("description_placeholders") == {
            "base_url": "http://127.0.0.1:123"
        }


async def test_options(hass):
    """Test updating options."""
    base_url = "http://127.0.0.1/"
    entry = MockConfigEntry(
        domain=DOMAIN, title=base_url, data={CONF_CONTROLLER: "http://127.0.0.1/"},
    )
    flow = VeraFlowHandler()
    flow.hass = hass
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await options_flow.async_step_init(
        {CONF_LIGHTS: "1,2;3  4 5_6bb7", CONF_EXCLUDE: "8,9;10  11 12_13bb14"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result.get("data") == {
        CONF_LIGHTS: [1, 2, 3, 4, 5, 6, 7],
        CONF_EXCLUDE: [8, 9, 10, 11, 12, 13, 14],
    }
