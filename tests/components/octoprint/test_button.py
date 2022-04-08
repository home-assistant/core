"""Test the OctoPrint buttons."""
from unittest.mock import patch

from pyoctoprintapi import OctoprintPrinterInfo
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.components.octoprint import OctoprintDataUpdateCoordinator
from homeassistant.components.octoprint.button import InvalidPrinterState
from homeassistant.components.octoprint.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_pause_job(hass: HomeAssistant):
    """Test the pause job button."""
    await init_integration(hass, BUTTON_DOMAIN)

    corrdinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN]["uuid"][
        "coordinator"
    ]

    # Test pausing the printer when it is printing
    with patch("pyoctoprintapi.OctoprintClient.pause_job") as pause_command:
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {"state": {"flags": {"printing": True}}, "temperature": []}
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_pause_job",
            },
            blocking=True,
        )

        assert len(pause_command.mock_calls) == 1

    # Test pausing the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.pause_job") as pause_command:
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {"state": {"flags": {"printing": False, "paused": True}}, "temperature": []}
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_pause_job",
            },
            blocking=True,
        )

        assert len(pause_command.mock_calls) == 0

    # Test pausing the printer when it is stopped
    with patch(
        "pyoctoprintapi.OctoprintClient.pause_job"
    ) as pause_command, pytest.raises(InvalidPrinterState):
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_pause_job",
            },
            blocking=True,
        )


async def test_resume_job(hass: HomeAssistant):
    """Test the resume job button."""
    await init_integration(hass, BUTTON_DOMAIN)

    corrdinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN]["uuid"][
        "coordinator"
    ]

    # Test resuming the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.resume_job") as resume_command:
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {"state": {"flags": {"printing": False, "paused": True}}, "temperature": []}
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_resume_job",
            },
            blocking=True,
        )

        assert len(resume_command.mock_calls) == 1

    # Test resuming the printer when it is printing
    with patch("pyoctoprintapi.OctoprintClient.resume_job") as resume_command:
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {"state": {"flags": {"printing": True, "paused": False}}, "temperature": []}
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_resume_job",
            },
            blocking=True,
        )

        assert len(resume_command.mock_calls) == 0

    # Test resuming the printer when it is stopped
    with patch(
        "pyoctoprintapi.OctoprintClient.resume_job"
    ) as resume_command, pytest.raises(InvalidPrinterState):
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_resume_job",
            },
            blocking=True,
        )


async def test_stop_job(hass: HomeAssistant):
    """Test the stop job button."""
    await init_integration(hass, BUTTON_DOMAIN)

    corrdinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN]["uuid"][
        "coordinator"
    ]

    # Test stopping the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.cancel_job") as stop_command:
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {"state": {"flags": {"printing": False, "paused": True}}, "temperature": []}
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_stop_job",
            },
            blocking=True,
        )

        assert len(stop_command.mock_calls) == 1

    # Test stopping the printer when it is printing
    with patch("pyoctoprintapi.OctoprintClient.cancel_job") as stop_command:
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {"state": {"flags": {"printing": True, "paused": False}}, "temperature": []}
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_stop_job",
            },
            blocking=True,
        )

        assert len(stop_command.mock_calls) == 1

    # Test stopping the printer when it is stopped
    with patch("pyoctoprintapi.OctoprintClient.cancel_job") as stop_command:
        corrdinator.data["printer"] = OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        )
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.octoprint_stop_job",
            },
            blocking=True,
        )

        assert len(stop_command.mock_calls) == 0
