"""Test the OctoPrint buttons."""

from unittest.mock import patch

from freezegun import freeze_time
from pyoctoprintapi import OctoprintPrinterInfo
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.octoprint import OctoprintDataUpdateCoordinator
from homeassistant.components.octoprint.button import InvalidPrinterState
from homeassistant.components.octoprint.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_pause_job(hass: HomeAssistant) -> None:
    """Test the pause job button."""
    await init_integration(hass, BUTTON_DOMAIN)

    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN]["uuid"][
        "coordinator"
    ]

    # Test pausing the printer when it is printing
    with patch("pyoctoprintapi.OctoprintClient.pause_job") as pause_command:
        coordinator.data["printer"] = OctoprintPrinterInfo(
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
        coordinator.data["printer"] = OctoprintPrinterInfo(
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
    with patch("pyoctoprintapi.OctoprintClient.pause_job") as pause_command:
        coordinator.data["printer"] = OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        )
        with pytest.raises(InvalidPrinterState):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {
                    ATTR_ENTITY_ID: "button.octoprint_pause_job",
                },
                blocking=True,
            )


async def test_resume_job(hass: HomeAssistant) -> None:
    """Test the resume job button."""
    await init_integration(hass, BUTTON_DOMAIN)

    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN]["uuid"][
        "coordinator"
    ]

    # Test resuming the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.resume_job") as resume_command:
        coordinator.data["printer"] = OctoprintPrinterInfo(
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
        coordinator.data["printer"] = OctoprintPrinterInfo(
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
    with patch("pyoctoprintapi.OctoprintClient.resume_job") as resume_command:
        coordinator.data["printer"] = OctoprintPrinterInfo(
            {
                "state": {"flags": {"printing": False, "paused": False}},
                "temperature": [],
            }
        )
        with pytest.raises(InvalidPrinterState):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {
                    ATTR_ENTITY_ID: "button.octoprint_resume_job",
                },
                blocking=True,
            )


async def test_stop_job(hass: HomeAssistant) -> None:
    """Test the stop job button."""
    await init_integration(hass, BUTTON_DOMAIN)

    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN]["uuid"][
        "coordinator"
    ]

    # Test stopping the printer when it is paused
    with patch("pyoctoprintapi.OctoprintClient.cancel_job") as stop_command:
        coordinator.data["printer"] = OctoprintPrinterInfo(
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
        coordinator.data["printer"] = OctoprintPrinterInfo(
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
        coordinator.data["printer"] = OctoprintPrinterInfo(
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


@freeze_time("2023-01-01 00:00")
async def test_shutdown_system(hass: HomeAssistant) -> None:
    """Test the shutdown system button."""
    await init_integration(hass, BUTTON_DOMAIN)

    entity_id = "button.octoprint_shutdown_system"

    # Test shutting down the system
    with patch(
        "homeassistant.components.octoprint.coordinator.OctoprintClient.shutdown"
    ) as shutdown_command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        assert len(shutdown_command.mock_calls) == 1

        state = hass.states.get(entity_id)
        assert state
        assert state.state == "2023-01-01T00:00:00+00:00"


@freeze_time("2023-01-01 00:00")
async def test_reboot_system(hass: HomeAssistant) -> None:
    """Test the reboot system button."""
    await init_integration(hass, BUTTON_DOMAIN)

    entity_id = "button.octoprint_reboot_system"

    # Test rebooting the system
    with patch(
        "homeassistant.components.octoprint.coordinator.OctoprintClient.reboot_system"
    ) as reboot_command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

        assert len(reboot_command.mock_calls) == 1

        state = hass.states.get(entity_id)
        assert state
        assert state.state == "2023-01-01T00:00:00+00:00"


@freeze_time("2023-01-01 00:00")
async def test_restart_octoprint(hass: HomeAssistant) -> None:
    """Test the restart octoprint button."""
    await init_integration(hass, BUTTON_DOMAIN)

    entity_id = "button.octoprint_restart_octoprint"

    # Test restarting octoprint
    with patch(
        "homeassistant.components.octoprint.coordinator.OctoprintClient.restart"
    ) as restart_command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

        assert len(restart_command.mock_calls) == 1

        state = hass.states.get(entity_id)
        assert state
        assert state.state == "2023-01-01T00:00:00+00:00"
