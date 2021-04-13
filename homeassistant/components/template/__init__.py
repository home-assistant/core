"""The template component."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from homeassistant import config as conf_util
from homeassistant.const import EVENT_HOMEASSISTANT_START, SERVICE_RELOAD
from homeassistant.core import CoreState, Event, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    discovery,
    trigger as trigger_helper,
    update_coordinator,
)
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.loader import async_get_integration

from .const import CONF_TRIGGER, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the template integration."""
    if DOMAIN in config:
        await _process_config(hass, config)

    async def _reload_config(call: Event) -> None:
        """Reload top-level + platforms."""
        try:
            unprocessed_conf = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        conf = await conf_util.async_process_component_config(
            hass, unprocessed_conf, await async_get_integration(hass, DOMAIN)
        )

        if conf is None:
            return

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

        if DOMAIN in conf:
            await _process_config(hass, conf)

        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_RELOAD, _reload_config
    )

    return True


async def _process_config(hass, hass_config):
    """Process config."""
    coordinators: list[TriggerUpdateCoordinator] | None = hass.data.pop(DOMAIN, None)

    # Remove old ones
    if coordinators:
        for coordinator in coordinators:
            coordinator.async_remove()

    async def init_coordinator(hass, conf_section):
        coordinator = TriggerUpdateCoordinator(hass, conf_section)
        await coordinator.async_setup(hass_config)
        return coordinator

    coordinator_tasks = []

    for conf_section in hass_config[DOMAIN]:
        if CONF_TRIGGER in conf_section:
            coordinator_tasks.append(init_coordinator(hass, conf_section))
            continue

        for platform_domain in PLATFORMS:
            if platform_domain in conf_section:
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass,
                        platform_domain,
                        DOMAIN,
                        {"entities": conf_section[platform_domain]},
                        hass_config,
                    )
                )

    if coordinator_tasks:
        hass.data[DOMAIN] = await asyncio.gather(*coordinator_tasks)


class TriggerUpdateCoordinator(update_coordinator.DataUpdateCoordinator):
    """Class to handle incoming data."""

    REMOVE_TRIGGER = object()

    def __init__(self, hass, config):
        """Instantiate trigger data."""
        super().__init__(hass, _LOGGER, name="Trigger Update Coordinator")
        self.config = config
        self._unsub_start: Callable[[], None] | None = None
        self._unsub_trigger: Callable[[], None] | None = None

    @property
    def unique_id(self) -> str | None:
        """Return unique ID for the entity."""
        return self.config.get("unique_id")

    @callback
    def async_remove(self):
        """Signal that the entities need to remove themselves."""
        if self._unsub_start:
            self._unsub_start()
        if self._unsub_trigger:
            self._unsub_trigger()

    async def async_setup(self, hass_config):
        """Set up the trigger and create entities."""
        if self.hass.state == CoreState.running:
            await self._attach_triggers()
        else:
            self._unsub_start = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, self._attach_triggers
            )

        for platform_domain in PLATFORMS:
            if platform_domain in self.config:
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
        if start_event is not None:
            self._unsub_start = None

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
