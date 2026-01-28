"""Vera tests."""

from unittest.mock import MagicMock, patch

import pyvera as pv
from requests.exceptions import RequestException

from homeassistant import config_entries
from homeassistant.components.vera.const import (
    CONF_CONTROLLER,
    CONF_LEGACY_UNIQUE_ID,
    DOMAIN,
)
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_async_step_user_success(hass: HomeAssistant) -> None:
    """Test user step success with device configuration."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        controller.serial_number = "serial_number_0"

        # Mock some devices
        device1 = MagicMock(spec=pv.VeraSwitch)
        device1.device_id = 12
        device1.name = "Switch 1"

        device2 = MagicMock(spec=pv.VeraSwitch)
        device2.device_id = 13
        device2.name = "Switch 2"

        device3 = MagicMock(spec=pv.VeraSensor)
        device3.device_id = 14
        device3.name = "Sensor 1"

        controller.get_devices = MagicMock(return_value=[device1, device2, device3])
        vera_controller_class_mock.return_value = controller

        # Step 1: Enter URL
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == config_entries.SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONTROLLER: "http://127.0.0.1:123/",
            },
        )

        # Step 2: Configure devices
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "devices"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LIGHTS: ["12", "13"],
                CONF_EXCLUDE: ["14"],
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:123"
        assert result["data"] == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_USER,
            CONF_LEGACY_UNIQUE_ID: False,
        }
        assert result["options"] == {
            CONF_LIGHTS: [12, 13],
            CONF_EXCLUDE: [14],
        }
        assert result["result"].unique_id == controller.serial_number

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries


async def test_async_step_user_no_devices(hass: HomeAssistant) -> None:
    """Test user step success with no devices."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock()
        controller.serial_number = "serial_number_0"
        controller.get_devices = MagicMock(return_value=[])
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == config_entries.SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONTROLLER: "http://127.0.0.1:123/",
            },
        )

        # Should skip device config and create entry directly
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:123"
        assert result["options"] == {
            CONF_LIGHTS: [],
            CONF_EXCLUDE: [],
        }


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

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:123"
        assert result["data"] == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_IMPORT,
            CONF_LEGACY_UNIQUE_ID: False,
        }
        assert result["result"].unique_id == controller.serial_number


async def test_async_step_import_success_with_legacy_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test import step success with legacy unique id."""
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

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:123"
        assert result["data"] == {
            CONF_CONTROLLER: "http://127.0.0.1:123",
            CONF_SOURCE: config_entries.SOURCE_IMPORT,
            CONF_LEGACY_UNIQUE_ID: True,
        }
        assert result["result"].unique_id == controller.serial_number


async def test_async_step_finish_error(hass: HomeAssistant) -> None:
    """Test user step with connection error."""
    with patch("pyvera.VeraController") as vera_controller_class_mock:
        controller = MagicMock()
        controller.refresh_data = MagicMock(side_effect=RequestException())
        vera_controller_class_mock.return_value = controller

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CONTROLLER: "http://127.0.0.1:123/",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == config_entries.SOURCE_USER
        assert result["errors"] == {"base": "cannot_connect"}


async def test_options(hass: HomeAssistant) -> None:
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LIGHTS: "1,2;3  4 5_6bb7",
            CONF_EXCLUDE: "8,9;10  11 12_13bb14",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_LIGHTS: [1, 2, 3, 4, 5, 6, 7],
        CONF_EXCLUDE: [8, 9, 10, 11, 12, 13, 14],
    }
