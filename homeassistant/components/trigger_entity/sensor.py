"""Trigger sensor entities."""
from __future__ import annotations

import logging

from homeassistant.components.trigger_entity import TriggerUpdateCoordinator
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import template, update_coordinator

from .config import CONF_STATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up trigger entities."""
    if discovery_info is None:
        raise HomeAssistantError("Platform setup not supported")

    async_add_entities(
        TriggerSensorEntity(discovery_info["coordinator"], config)
        for config in discovery_info["entities"]
    )


class TriggerSensorEntity(update_coordinator.CoordinatorEntity):
    """Sensor entity based on trigger data."""

    def __init__(self, coordinator: TriggerUpdateCoordinator, config: dict):
        """Initialize the entity."""
        super().__init__(coordinator)
        object_id = config.get(CONF_UNIQUE_ID)

        if object_id and coordinator.unique_id:
            self._unique_id = f"{coordinator.unique_id}-{object_id}"
        else:
            self._unique_id = None

            if object_id:
                _LOGGER.warning(
                    "Ignoring unique ID %s because the config has no unique ID configured",
                    object_id,
                )

        self._config = config
        self._rendered = {}

    @property
    def name(self):
        """Name of the entity."""
        name = self._config.get(CONF_NAME)
        if name is not None:
            return name
        return self._config.get(CONF_UNIQUE_ID)

    @property
    def unique_id(self):
        """Return unique ID of the entity."""
        return self._unique_id

    @property
    def device_class(self):
        """Return device class of the entity."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def available(self):
        """Return availability of the entity."""
        return self._rendered is not None

    @property
    def state(self):
        """State of the entity."""
        return self._rendered.get(CONF_STATE)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        template.attach(self.hass, self._config)
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            rendered = {}

            for key in (CONF_STATE,):
                if key in self._config:
                    rendered[key] = self._config[key].async_render(
                        self.coordinator.data["run_variables"], parse_result=False
                    )

            self._rendered = rendered
        except template.TemplateError as err:
            _LOGGER.error("Error rendering template: %s", err)
            self._rendered = None

        self.async_set_context(self.coordinator.data["context"])
        self.async_write_ha_state()
