"""Data update coordinator for trigger based template entities."""
from collections.abc import Callable
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import CoreState, callback
from homeassistant.helpers import discovery, trigger as trigger_helper
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_TRIGGER, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class TriggerUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for trigger based template entities."""

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

    async def async_setup(self, hass_config: ConfigType) -> None:
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
