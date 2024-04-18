"""Test the Home Assistant SkyConnect config flow failure cases."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from universal_silabs_flasher.const import ApplicationType

from homeassistant.components import usb
from homeassistant.components.hassio.addon_manager import (
    AddonError,
    AddonInfo,
    AddonState,
)
from homeassistant.components.homeassistant_sky_connect.config_flow import (
    STEP_PICK_FIRMWARE_ZIGBEE,
)
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.components.homeassistant_sky_connect.util import (
    get_zigbee_flasher_addon_manager,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .test_config_flow import USB_DATA_ZBT1, delayed_side_effect


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_cannot_probe_firmware(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test failure case when firmware cannot be probed."""

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=None,
    ):
        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )

        # Probing fails
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "unsupported_firmware"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee_not_hassio_wrong_firmware(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test when the stick is used with a non-hassio setup but the firmware is bad."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "not_hassio"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee_flasher_addon_info_fails(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test failure case when flasher addon cannot be installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.addon_name = "Silicon Labs Flasher"
    mock_flasher_manager.async_get_addon_info.side_effect = AddonError()

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        # Cannot get addon info
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "addon_info_failed"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee_flasher_addon_install_fails(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test failure case when flasher addon cannot be installed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.addon_name = "Silicon Labs Flasher"
    mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    )
    mock_flasher_manager.async_install_addon_waiting = AsyncMock(
        side_effect=AddonError()
    )

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )

        # Cannot install addon
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "addon_install_failed"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee_flasher_addon_set_config_fails(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test failure case when flasher addon cannot be configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.addon_name = "Silicon Labs Flasher"
    mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    )
    mock_flasher_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_set_addon_options = AsyncMock(side_effect=AddonError())

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "addon_set_config_failed"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee_flasher_run_fails(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test failure case when flasher addon fails to run."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.addon_name = "Silicon Labs Flasher"
    mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    )
    mock_flasher_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_start_addon_waiting = AsyncMock(side_effect=AddonError())

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "addon_start_failed"


@pytest.mark.parametrize(
    ("usb_data", "model"),
    [
        (USB_DATA_ZBT1, "Home Assistant Connect ZBT-1"),
    ],
)
async def test_config_flow_zigbee_flasher_uninstall_fails(
    usb_data: usb.UsbServiceInfo, model: str, hass: HomeAssistant
) -> None:
    """Test failure case when flasher addon uninstall fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "usb"}, data=usb_data
    )

    with patch(
        "homeassistant.components.homeassistant_sky_connect.config_flow.probe_silabs_firmware_type",
        return_value=ApplicationType.SPINEL,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    mock_flasher_manager = Mock(spec_set=get_zigbee_flasher_addon_manager(hass))
    mock_flasher_manager.addon_name = "Silicon Labs Flasher"
    mock_flasher_manager.async_get_addon_info.return_value = AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    )
    mock_flasher_manager.async_install_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_start_addon_waiting = AsyncMock(
        side_effect=delayed_side_effect()
    )
    mock_flasher_manager.async_uninstall_addon_waiting = AsyncMock(
        side_effect=AddonError()
    )

    with (
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.get_zigbee_flasher_addon_manager",
            return_value=mock_flasher_manager,
        ),
        patch(
            "homeassistant.components.homeassistant_sky_connect.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": STEP_PICK_FIRMWARE_ZIGBEE},
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done(wait_background_tasks=True)

        # Uninstall failure isn't critical
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm_zigbee"
