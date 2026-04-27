"""Tests for iZone."""

from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components.izone.const import IZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_not_found(hass: HomeAssistant) -> None:
    """Test no device found during broadcast discovery."""

    with patch(
        "homeassistant.components.izone.config_flow._async_discover_controllers",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()


async def test_found(hass: HomeAssistant) -> None:
    """Test finding iZone controller via broadcast discovery."""

    controller = Mock()
    controller.device_uid = "000013170"
    controller.device_ip = "192.168.1.20"

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={controller.device_uid: controller},
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "iZone 000013170"
        assert result["data"] == {"host": "192.168.1.20"}

        await hass.async_block_till_done()

    mock_setup.assert_called_once()


async def test_manual_host_success(hass: HomeAssistant) -> None:
    """Test successful manual host validation."""
    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.config_flow._async_get_controller_uid",
            return_value="000013170",
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "izone.local"}
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000013170"
    assert result["data"] == {"host": "izone.local"}


async def test_manual_host_failed_validation(hass: HomeAssistant) -> None:
    """Test failed manual host validation shows cannot_connect."""
    with patch(
        "homeassistant.components.izone.config_flow._async_get_controller_uid",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "bad-host"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_import_discovers_and_creates_entry(hass: HomeAssistant) -> None:
    """Test YAML import discovers a controller and creates an entry."""
    controller = Mock()
    controller.device_uid = "000013170"
    controller.device_ip = "192.168.1.20"

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={controller.device_uid: controller},
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000013170"
    assert result["data"] == {"host": "192.168.1.20"}


async def test_homekit_confirm_uses_discovered_host(hass: HomeAssistant) -> None:
    """Test HomeKit flow confirms and uses the discovered host when valid."""
    controller = Mock()
    controller.device_uid = "000013170"
    controller.device_ip = "10.0.0.90"

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
        patch(
            "homeassistant.components.izone.config_flow._async_discover_controllers",
            return_value={controller.device_uid: controller},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={
                "host": "13.238.133.246",
                "properties": {"md": "iZone 000013170"},
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        flow = next(
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert flow["context"]["title_placeholders"] == {"name": "iZone 000013170"}
        assert result["description_placeholders"] == {
            "controller_uid": "000013170",
            "host": "10.0.0.90",
        }

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000013170"
    assert result["data"] == {"host": "10.0.0.90"}


async def test_multiple_entries_allowed(hass: HomeAssistant) -> None:
    """Test multiple iZone controllers can be configured."""
    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.config_flow._async_get_controller_uid",
            side_effect=["000013170", "000025841"],
        ),
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "izone-1.local"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "iZone 000013170"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "izone-2.local"}
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000025841"
    assert result["data"] == {"host": "izone-2.local"}


async def test_reuses_existing_discovery_service(hass: HomeAssistant) -> None:
    """Test config flow reuses the running discovery service."""
    controller = Mock()
    controller.device_uid = "000025841"
    controller.device_ip = "192.168.1.21"
    discovery_service = Mock()
    discovery_service.pi_disco.controllers = {controller.device_uid: controller}
    hass.data["izone_discovery"] = discovery_service

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.config_flow.pizone.discovery",
        ) as mock_pizone_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000025841"
    assert result["data"] == {"host": "192.168.1.21"}
    mock_pizone_discovery.assert_not_called()


async def test_manual_host_uses_shared_discovery_service(hass: HomeAssistant) -> None:
    """Test manual host setup resolves UID from the shared discovery service."""
    controller = Mock()
    controller.device_uid = "000025841"
    controller.device_ip = "192.168.1.21"
    discovery_service = Mock()
    discovery_service.pi_disco.controllers = {controller.device_uid: controller}
    hass.data["izone_discovery"] = discovery_service

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.izone.config_flow.pizone.discovery",
        ) as mock_pizone_discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.168.1.21"}
        )

        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "iZone 000025841"
    assert result["data"] == {"host": "192.168.1.21"}
    mock_pizone_discovery.assert_not_called()
