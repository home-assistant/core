"""Trigger entities."""

import logging
from typing import Optional

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    trigger,
    update_coordinator,
)

DOMAIN = "trigger"


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(DOMAIN): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional("unique_id"): cv.string,
                        vol.Optional("variables"): cv.SCRIPT_VARIABLES_SCHEMA,
                        vol.Required("trigger"): cv.TRIGGER_SCHEMA,
                        vol.Optional("sensor"): vol.Schema(
                            {
                                str: vol.Schema(
                                    {
                                        vol.Optional("name"): cv.string,
                                        vol.Required("value_template"): cv.template,
                                    }
                                )
                            }
                        ),
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the trigger integration."""
    for conf in config[DOMAIN]:
        coordinator = TriggerUpdateCoordinator(hass, conf)
        await coordinator.async_setup(config)

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
        return self.config.get("unique_id")

    async def async_setup(self, hass_config):
        """Set up the trigger and create entities."""
        home_assistant_start = True

        self._unsub_trigger = await trigger.async_initialize_triggers(
            self.hass,
            # TODO move this to trigger/config.py
            await trigger.async_validate_trigger_config(
                self.hass, self.config["trigger"]
            ),
            self._handle_triggered,
            DOMAIN,
            self.name,
            self.logger.log,
            home_assistant_start,
            self.config.get("variables"),
        )

        self.hass.async_create_task(
            discovery.async_load_platform(
                self.hass,
                "sensor",
                DOMAIN,
                {"coordinator": self, "entities": self.config["sensor"]},
                hass_config,
            )
        )

    @callback
    def _handle_triggered(self, run_variables, context=None):
        self.async_set_updated_data(
            {"run_variables": run_variables, "context": context}
        )
