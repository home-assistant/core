"""Vera tests."""
from unittest.mock import MagicMock

from mock import patch
from requests.exceptions import RequestException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vera import CONF_CONTROLLER, DOMAIN
from homeassistant.components.vera.config_flow import VeraFlowHandler
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS, CONF_SOURCE
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
            data={
                CONF_CONTROLLER: "http://127.0.0.1:123/",
                CONF_LIGHTS: "12 13",
                CONF_EXCLUDE: "14 15",
            },
        )
        assert result.get("type") == RESULT_TYPE_CREATE_ENTRY
        assert result.get("title") == "http://127.0.0.1:123"
        assert result.get("data") == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_USER,
            CONF_LIGHTS: ["12", "13"],
            CONF_EXCLUDE: ["14", "15"],
        }
        assert result.get("result").unique_id == controller.serial_number

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries


async def test_async_step_user_already_setup(hass: HomeAssistant) -> None:
    """Test function."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={}, unique_id="12345")
    entry.add_to_hass(hass)

    handler = VeraFlowHandler()
    handler.context = {}
    handler.hass = hass

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
        assert result.get("data") == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_IMPORT,
        }
        assert result.get("result").unique_id == controller.serial_number


async def test_async_step_import_alredy_setup(hass: HomeAssistant) -> None:
    """Test function."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={}, unique_id="12345")
    entry.add_to_hass(hass)

    handler = VeraFlowHandler()
    handler.context = {}
    handler.hass = hass

    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        controller.serial_number = "12345"
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_CONTROLLER: "http://localhost:445"},
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


async def test_options_available(hass: HomeAssistant) -> None:
    """Test function."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        controller.serial_number = "serial_number_1"
        vera_controller_class_mock.return_value = controller

        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_CONTROLLER: "http://127.0.0.1:123/"},
        )
        entries = hass.config_entries.async_entries(DOMAIN)

        await hass.config_entries.options.async_init(
            entries[0].entry_id, context={}, data={}
        )


async def test_options(hass):
    """Test updating options."""
    base_url = "http://127.0.0.1/"
    entry = MockConfigEntry(
        domain=DOMAIN, title=base_url, data={CONF_CONTROLLER: "http://127.0.0.1/"},
    )
    entry.options[CONF_LIGHTS] = [1, 2, 3]
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": "test"},
        data={CONF_LIGHTS: "1,2;3  4 5_6bb7", CONF_EXCLUDE: "8,9;10  11 12_13bb14"},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result.get("data") == {
        CONF_LIGHTS: ["1", "2", "3", "4", "5", "6", "7"],
        CONF_EXCLUDE: ["8", "9", "10", "11", "12", "13", "14"],
    }
