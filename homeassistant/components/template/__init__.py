"""The template component."""
import logging
from typing import Optional

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, callback
from homeassistant.helpers import (
    discovery,
    trigger as trigger_helper,
    update_coordinator,
)
from homeassistant.helpers.reload import async_setup_reload_service

from .const import CONF_TRIGGER, DOMAIN, PLATFORMS


async def async_setup(hass, config):
    """Set up the template integration."""
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            coordinator = TriggerUpdateCoordinator(hass, conf)
            await coordinator.async_setup(config)

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
            self._handle_triggered,
            DOMAIN,
            self.name,
            self.logger.log,
            start_event is not None,
        )

    @callback
    def _handle_triggered(self, run_variables, context=None):
        self.async_set_updated_data(
            {"run_variables": run_variables, "context": context}
        )
