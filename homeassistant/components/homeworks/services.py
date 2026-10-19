"""Services for the Lutron Homeworks Series 4 and 8 integration."""

import asyncio
import logging
from typing import TYPE_CHECKING

import probatio

from homeassistant.const import CONF_COMMAND
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError

from .const import CONF_CONTROLLER_ID, DOMAIN

if TYPE_CHECKING:
    from . import HomeworksConfigEntry, HomeworksData

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_CONTROLLER_ID): str,
        probatio.Required(CONF_COMMAND): probatio.All(probatio.EnsureList(), [str]),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Lutron Homeworks Series 4 and 8 integration."""

    hass.services.async_register(
        DOMAIN,
        "send_command",
        async_send_command,
        schema=SERVICE_SEND_COMMAND_SCHEMA,
    )


async def async_send_command(service_call: ServiceCall) -> None:
    """Send command to a controller."""

    def get_controller_ids() -> list[str]:
        """Get homeworks data for the specified controller ID."""
        return [
            entry.runtime_data.controller_id
            for entry in service_call.hass.config_entries.async_loaded_entries(DOMAIN)
        ]

    def get_homeworks_data(controller_id: str) -> HomeworksData | None:
        """Get homeworks data for the specified controller ID."""
        entry: HomeworksConfigEntry
        for entry in service_call.hass.config_entries.async_loaded_entries(DOMAIN):
            if entry.runtime_data.controller_id == controller_id:
                return entry.runtime_data
        return None

    homeworks_data = get_homeworks_data(service_call.data[CONF_CONTROLLER_ID])
    if not homeworks_data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_controller_id",
            translation_placeholders={
                "controller_id": service_call.data[CONF_CONTROLLER_ID],
                "controller_ids": ",".join(get_controller_ids()),
            },
        )

    commands = service_call.data[CONF_COMMAND]
    _LOGGER.debug("Send commands: %s", commands)
    for command in commands:
        if command.lower().startswith("delay"):
            delay = int(command.partition(" ")[2])
            _LOGGER.debug("Sleeping for %s ms", delay)
            await asyncio.sleep(delay / 1000)
        else:
            _LOGGER.debug("Sending command '%s'", command)
            await service_call.hass.async_add_executor_job(
                homeworks_data.controller._send,  # noqa: SLF001
                command,
            )
