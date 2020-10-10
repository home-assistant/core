"""Vera tests."""
from requests.exceptions import RequestException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vera import CONF_CONTROLLER, CONF_LEGACY_UNIQUE_ID, DOMAIN
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry, mock_registry


async def test_async_step_user_success(hass: HomeAssistant) -> None:
    """Test user step success."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        controller.serial_number = "serial_number_0"
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == config_entries.SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONTROLLER: "http://127.0.0.1:123/",
                CONF_LIGHTS: "12 13",
                CONF_EXCLUDE: "14 15",
            },
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:123"
        assert result["data"] == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_USER,
            CONF_LIGHTS: [12, 13],
            CONF_EXCLUDE: [14, 15],
            CONF_LEGACY_UNIQUE_ID: False,
        }
        assert result["result"].unique_id == controller.serial_number

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries


async def test_async_step_import_success(hass: HomeAssistant) -> None:
    """Test import step success."""
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

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:123"
        assert result["data"] == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_IMPORT,
            CONF_LEGACY_UNIQUE_ID: False,
        }
        assert result["result"].unique_id == controller.serial_number


async def test_async_step_import_success_with_legacy_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test import step success with legacy unique id."""
    entity_registry = mock_registry(hass)
    entity_registry.async_get_or_create(
        domain="switch", platform=DOMAIN, unique_id="12"
    )

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

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:123"
        assert result["data"] == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_IMPORT,
            CONF_LEGACY_UNIQUE_ID: True,
        }
        assert result["result"].unique_id == controller.serial_number


async def test_async_step_finish_error(hass: HomeAssistant) -> None:
    """Test finish step with error."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock(side_effect=RequestException())
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_CONTROLLER: "http://127.0.0.1:123/"},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"
        assert result["description_placeholders"] == {
            "base_url": "http://127.0.0.1:123"
        }


async def test_options(hass):
    """Test updating options."""
    base_url = "http://127.0.0.1/"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=base_url,
        data={CONF_CONTROLLER: "http://127.0.0.1/"},
        options={CONF_LIGHTS: [1, 2, 3]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LIGHTS: "1,2;3  4 5_6bb7",
            CONF_EXCLUDE: "8,9;10  11 12_13bb14",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_LIGHTS: [1, 2, 3, 4, 5, 6, 7],
        CONF_EXCLUDE: [8, 9, 10, 11, 12, 13, 14],
    }
