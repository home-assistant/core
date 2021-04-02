"""The template component."""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, callback
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_component,
    trigger as trigger_helper,
    update_coordinator,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.service import async_register_admin_service

from .const import CONF_TRIGGER, DOMAIN, PLATFORMS

ATTR_VARIABLES = "variables"
SERVICE_TRIGGER = "trigger"


async def async_setup(hass, config):
    """Set up the template integration."""
    coordinators = []

    if DOMAIN in config:
        for conf in config[DOMAIN]:
            coordinator = TriggerUpdateCoordinator(hass, conf)
            await coordinator.async_setup(config)
            coordinators.append(coordinator)

    async def trigger_coordinator(service_call):
        """Trigger an update coordinator."""
        entity_id = service_call.data[ATTR_ENTITY_ID]

        found = None

        for coordinator in coordinators:
            if entity_id in coordinator.entity_ids:
                found = coordinator
                break

        if found is None:
            if ATTR_VARIABLES in service_call.data:
                raise vol.Invalid(
                    "Passing variables to state machine based template entities is not allowed"
                )
            await entity_component.async_update_entity(hass, entity_id)
            return

        found.handle_triggered(
            {
                **service_call.data.get(ATTR_VARIABLES, {}),
                "trigger": {"platform": None},
            },
            context=service_call.context,
        )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_TRIGGER,
        trigger_coordinator,
        vol.Schema(
            {
                vol.Required(ATTR_ENTITY_ID): cv.entity_id,
                vol.Optional(ATTR_VARIABLES): dict,
            }
        ),
    )

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    return True


class TriggerUpdateCoordinator(update_coordinator.DataUpdateCoordinator):
    """Class to handle incoming data."""

    def __init__(self, hass, config):
        """Instantiate trigger data."""
        super().__init__(
            hass, logging.getLogger(__name__), name="Trigger Update Coordinator"
        )
        self.config = config
        self._unsub_trigger = None
        self.entity_ids = set()

    @property
    def unique_id(self) -> Optional[str]:
        """Return unique ID for the entity."""
        return self.config.get("unique_id")

    async def async_setup(self, hass_config):
        """Set up the trigger and create entities."""
        if self.hass.state == CoreState.running:
            await self._attach_triggers()
        else:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, self._attach_triggers
            )

        for platform_domain in (SENSOR_DOMAIN,):
            self.hass.async_create_task(
                discovery.async_load_platform(
                    self.hass,
                    platform_domain,
                    DOMAIN,
                    {"coordinator": self, "entities": self.config[platform_domain]},
                    hass_config,
                )
            )

    async def _attach_triggers(self, start_event=None) -> None:
        """Attach the triggers."""
        self._unsub_trigger = await trigger_helper.async_initialize_triggers(
            self.hass,
            self.config[CONF_TRIGGER],
            self.handle_triggered,
            DOMAIN,
            self.name,
            self.logger.log,
            start_event is not None,
        )

    @callback
    def handle_triggered(self, run_variables, context=None):
        """Handle a trigger firing."""
        self.async_set_updated_data(
            {"run_variables": run_variables, "context": context}
        )
