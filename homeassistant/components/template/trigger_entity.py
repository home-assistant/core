"""Trigger entity."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template, update_coordinator

from . import TriggerUpdateCoordinator
from .const import CONF_ATTRIBUTES, CONF_AVAILABILITY, CONF_PICTURE


class TriggerEntity(update_coordinator.CoordinatorEntity):
    """Template entity based on trigger data."""

    domain = ""
    extra_template_keys: tuple | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ):
        """Initialize the entity."""
        super().__init__(coordinator)

        entity_unique_id = config.get(CONF_UNIQUE_ID)

        if entity_unique_id and coordinator.unique_id:
            self._unique_id = f"{coordinator.unique_id}-{entity_unique_id}"
        else:
            self._unique_id = entity_unique_id

        self._config = config

        self._static_rendered = {}
        self._to_render = []

        for itm in (
            CONF_NAME,
            CONF_ICON,
            CONF_PICTURE,
            CONF_AVAILABILITY,
        ):
            if itm not in config:
                continue

            if config[itm].is_static:
                self._static_rendered[itm] = config[itm].template
            else:
                self._to_render.append(itm)

        if self.extra_template_keys is not None:
            self._to_render.extend(self.extra_template_keys)

        # We make a copy so our initial render is 'unknown' and not 'unavailable'
        self._rendered = dict(self._static_rendered)
        self._parse_result = set()

    @property
    def name(self):
        """Name of the entity."""
        return self._rendered.get(CONF_NAME)

    @property
    def unique_id(self):
        """Return unique ID of the entity."""
        return self._unique_id

    @property
    def device_class(self):
        """Return device class of the entity."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def icon(self) -> str | None:
        """Return icon."""
        return self._rendered.get(CONF_ICON)

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        return self._rendered.get(CONF_PICTURE)

    @property
    def available(self):
        """Return availability of the entity."""
        return (
            self._rendered is not self._static_rendered
            and
            # Check against False so `None` is ok
            self._rendered.get(CONF_AVAILABILITY) is not False
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        return self._rendered.get(CONF_ATTRIBUTES)

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        template.attach(self.hass, self._config)
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._process_data()

    @callback
    def _process_data(self) -> None:
        """Process new data."""
        try:
            rendered = dict(self._static_rendered)

            for key in self._to_render:
                rendered[key] = self._config[key].async_render(
                    self.coordinator.data["run_variables"],
                    parse_result=key in self._parse_result,
                )

            if CONF_ATTRIBUTES in self._config:
                rendered[CONF_ATTRIBUTES] = template.render_complex(
                    self._config[CONF_ATTRIBUTES],
                    self.coordinator.data["run_variables"],
                )

            self._rendered = rendered
        except template.TemplateError as err:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").error(
                "Error rendering %s template for %s: %s", key, self.entity_id, err
            )
            self._rendered = self._static_rendered

        self.async_set_context(self.coordinator.data["context"])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._process_data()
        self.async_write_ha_state()
