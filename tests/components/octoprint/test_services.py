"""Test the OctoPrint services."""
from unittest.mock import patch

from pyoctoprintapi import OctoprintPrinterInfo
import pytest

from homeassistant.components.octoprint import InvalidPrinterState
from homeassistant.components.octoprint.const import (
    DOMAIN,
    SERVICE_PAUSE_JOB,
    SERVICE_RESUME_JOB,
    SERVICE_STOP_JOB,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get as async_get_dev_reg,
)

from . import init_integration


async def test_pause_job(hass):
    """Test the set_config_parameter service."""
    await init_integration(hass, "sensor")

    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, "uuid")[0]

    # Test pausing the printer when it is printing
    with patch("pyoctoprintapi.OctoprintClient.pause_job") as pause_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {"state": {"flags": {"printing": True}}, "temperature": []}
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PAUSE_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )

        assert len(pause_command.mock_calls) == 1

    # Test pausing the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.pause_job") as pause_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {"state": {"flags": {"printing": False, "paused": True}}, "temperature": []}
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PAUSE_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )

        assert len(pause_command.mock_calls) == 0

    # Test pausing the printer when it is stopped
    with patch("pyoctoprintapi.OctoprintClient.pause_job") as pause_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        ),
    ), pytest.raises(InvalidPrinterState):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PAUSE_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )


async def test_resume_job(hass):
    """Test the set_config_parameter service."""
    await init_integration(hass, "sensor")

    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, "uuid")[0]

    # Test resuming the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.resume_job") as resume_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {"state": {"flags": {"printing": False, "paused": True}}, "temperature": []}
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESUME_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )

        assert len(resume_command.mock_calls) == 1

    # Test resuming the printer when it is printing
    with patch("pyoctoprintapi.OctoprintClient.resume_job") as resume_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {"state": {"flags": {"printing": True, "paused": False}}, "temperature": []}
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESUME_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )

        assert len(resume_command.mock_calls) == 0

    # Test resuming the printer when it is stopped
    with patch("pyoctoprintapi.OctoprintClient.resume_job") as resume_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        ),
    ), pytest.raises(InvalidPrinterState):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESUME_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )


async def test_stop_job(hass):
    """Test the set_config_parameter service."""
    await init_integration(hass, "sensor")

    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, "uuid")[0]

    # Test stopping the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.cancel_job") as stop_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {"state": {"flags": {"printing": False, "paused": True}}, "temperature": []}
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )

        assert len(stop_command.mock_calls) == 1

    # Test resuming the printer when it is printing
    with patch("pyoctoprintapi.OctoprintClient.cancel_job") as stop_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {"state": {"flags": {"printing": True, "paused": False}}, "temperature": []}
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )

        assert len(stop_command.mock_calls) == 1

    # Test resuming the printer when it is stopped
    with patch("pyoctoprintapi.OctoprintClient.cancel_job") as stop_command, patch(
        "pyoctoprintapi.OctoprintClient.get_printer_info",
        return_value=OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_JOB,
            {
                ATTR_DEVICE_ID: device.id,
            },
            blocking=True,
        )

        assert len(stop_command.mock_calls) == 0
