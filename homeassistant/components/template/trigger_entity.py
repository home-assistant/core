"""Trigger entity."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template, update_coordinator
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import (
    TriggerUpdateCoordinator,
    convert_attribute_from_string,
    convert_attribute_to_string,
)
from .const import CONF_ATTRIBUTES, CONF_AVAILABILITY, CONF_PICTURE, CONF_RESTORE


class TriggerEntity(CoordinatorEntity[TriggerUpdateCoordinator]):
    """Template entity based on trigger data."""

    domain: str
    extra_template_keys: tuple | None = None
    extra_template_keys_complex: tuple | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        entity_unique_id = config.get(CONF_UNIQUE_ID)

        self._unique_id: str | None
        if entity_unique_id and coordinator.unique_id:
            self._unique_id = f"{coordinator.unique_id}-{entity_unique_id}"
        else:
            self._unique_id = entity_unique_id

        self._config = config

        self._static_rendered = {}
        self._to_render_simple = []
        self._to_render_complex: list[str] = []

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
                self._to_render_simple.append(itm)

        if self.extra_template_keys is not None:
            self._to_render_simple.extend(self.extra_template_keys)

        if self.extra_template_keys_complex is not None:
            self._to_render_complex.extend(self.extra_template_keys_complex)

        # We make a copy so our initial render is 'unknown' and not 'unavailable'
        self._rendered = dict(self._static_rendered)
        self._parse_result = {CONF_AVAILABILITY}
        self._restore = config.get(CONF_RESTORE)

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

            for key in self._to_render_simple:
                rendered[key] = self._config[key].async_render(
                    self.coordinator.data["run_variables"],
                    parse_result=key in self._parse_result,
                )

            for key in self._to_render_complex:
                rendered[key] = template.render_complex(
                    self._config[key],
                    self.coordinator.data["run_variables"],
                )

            if CONF_ATTRIBUTES in self._config:
                rendered[CONF_ATTRIBUTES] = template.render_complex(
                    self._config[CONF_ATTRIBUTES],
                    self.coordinator.data["run_variables"],
                )

            self._rendered = rendered
        except TemplateError as err:
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


class TriggerRestoreEntity(TriggerEntity, RestoreEntity):
    """Trigger Entity that restores data."""

    async def restore_entity(
        self,
    ) -> tuple[State | None, dict[str, Any] | None]:
        """Restore the entity."""

        if not self._restore:
            return None, None

        if (last_sensor_state := await self.async_get_last_state()) is None:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "No state found to restore for entity %s", self.entity_id
            )
            return None, None

        if (last_sensor_data := await self.async_get_last_rendered_data()) is None:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "No extra data found to restore for entity %s", self.entity_id
            )
            return last_sensor_state, None

        # Restore all attributes.
        logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
            "Restoring entity %s", self.entity_id
        )

        for key in self._to_render_simple:
            try:
                value = last_sensor_data[key]
            except KeyError:
                logging.getLogger(
                    f"{__package__}.{self.entity_id.split('.')[0]}"
                ).debug(
                    "Did not retrieve value for attribute %s for entity %s",
                    key,
                    self.entity_id,
                )
                continue

            self._rendered[key] = value
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "Restored attribute %s with value %s for entity %s",
                key,
                value,
                self.entity_id,
            )

        for key in self._to_render_complex:
            try:
                value = last_sensor_data[key]
            except KeyError:
                logging.getLogger(
                    f"{__package__}.{self.entity_id.split('.')[0]}"
                ).debug(
                    "Did not retrieve value for attribute %s for entity %s",
                    key,
                    self.entity_id,
                )
                continue

            self._rendered[key] = value
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "Restored attribute %s with value %s for entity %s",
                key,
                value,
                self.entity_id,
            )

        if CONF_ATTRIBUTES in last_sensor_data:
            for key in self._config.get(CONF_ATTRIBUTES, {}):
                try:
                    value = last_sensor_data[CONF_ATTRIBUTES][key]
                except KeyError:
                    logging.getLogger(
                        f"{__package__}.{self.entity_id.split('.')[0]}"
                    ).debug(
                        "Did not retrieve value for attribute %s for entity %s",
                        key,
                        self.entity_id,
                    )
                    continue

                self._rendered.setdefault(CONF_ATTRIBUTES, {})
                self._rendered[CONF_ATTRIBUTES][key] = value
                logging.getLogger(
                    f"{__package__}.{self.entity_id.split('.')[0]}"
                ).debug(
                    "Restored attribute %s with value %s for entity %s",
                    key,
                    value,
                    self.entity_id,
                )

        return last_sensor_state, last_sensor_data

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await self.restore_entity()
        await super().async_added_to_hass()

    @property
    def extra_restore_state_data(self) -> TriggerExtraStoredData | None:
        """Return sensor specific state data to be restored."""
        return (
            TriggerExtraStoredData(self._rendered)
            if self._restore
            else TriggerExtraStoredData(None)
        )

    async def async_get_last_rendered_data(self) -> dict[str, Any] | None:
        """Restore native_value and native_unit_of_measurement."""
        if not self._restore:
            return None

        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return TriggerExtraStoredData(None).from_dict(
            restored_last_extra_data.as_dict()
        )


@dataclass
class TriggerExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    rendered_values: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the sensor data."""
        if self.rendered_values is None:
            return {}

        dict_values: dict[str, Any] = {}
        for key, value in self.rendered_values.items():
            value = convert_attribute_to_string(value)
            logging.getLogger(f"{__package__}").info(
                "Storing attribute %s with value %s",
                key,
                value,
            )
            dict_values.update({key: value})

        return dict_values

    @staticmethod
    def from_dict(restored: dict[str, Any]) -> dict[str, Any]:
        """Initialize a stored sensor state from a dict."""
        dict_values: dict[str, Any] = {}
        for key, value in restored.items():
            value = convert_attribute_from_string(value)
            logging.getLogger(f"{__package__}").info(
                "Retrieved attribute %s with value %s",
                key,
                value,
            )
            dict_values.update({key: value})

        return dict_values
