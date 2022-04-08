"""Trigger entity."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.restore_state import (
    ExtraStoredData,
    RestoreEntity,
    RestoreStateData,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TemplateJSONDecoder, TemplateJSONEncoder, TriggerUpdateCoordinator
from .const import CONF_ATTRIBUTES, CONF_AVAILABILITY, CONF_PICTURE, CONF_RESTORE

CONF_TO_ATTRIBUTE = {
    CONF_ICON: ATTR_ICON,
    CONF_NAME: ATTR_FRIENDLY_NAME,
    CONF_PICTURE: ATTR_ENTITY_PICTURE,
}


class TriggerEntity(CoordinatorEntity[TriggerUpdateCoordinator], RestoreEntity):
    """Template entity based on trigger data."""

    domain: str
    extra_template_keys: tuple | None = None
    extra_template_keys_complex: tuple | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
        save_additional_attributes: list[str] | None = None,
        always_save_state: bool = False,
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
            CONF_AVAILABILITY,
            CONF_ICON,
            CONF_NAME,
            CONF_PICTURE,
        ):
            if itm not in config:
                continue

            if config[itm].is_static:
                self._static_rendered[itm] = config[itm].template
            else:
                self._to_render_simple.append(itm)

        self._extra_save_rendered: list = [CONF_AVAILABILITY]
        if self.extra_template_keys is not None:
            self._to_render_simple.extend(self.extra_template_keys)
            self._extra_save_rendered.extend(list(self.extra_template_keys))

        if self.extra_template_keys_complex is not None:
            self._to_render_complex.extend(self.extra_template_keys_complex)
            self._extra_save_rendered.extend(list(self.extra_template_keys_complex))

        # We make a copy so our initial render is 'unknown' and not 'unavailable'
        self._rendered = dict(self._static_rendered)
        self._parse_result = {CONF_AVAILABILITY}
        self._save_extra_data: bool = True
        self._extra_save_data: list = save_additional_attributes or []
        self.restore = config.get(CONF_RESTORE, False)
        self._always_save_state = always_save_state

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

    @property
    def save_extra_data(self) -> bool:
        """Return if extra attributes data is to be saved or not."""
        return self._save_extra_data

    async def async_internal_added_to_hass(self) -> None:
        """Register this entity as a restorable entity."""
        _, data = await asyncio.gather(
            super().async_internal_added_to_hass(),
            RestoreStateData.async_get_instance(self.hass),
        )
        if not self.restore and not self._always_save_state:
            # Remove this entity for saving state and remove from
            # last_states if entity does not need to be restored
            # nor does its state always have to be saved irrespective
            # of restore.
            data.entities.pop(self.entity_id)
            data.last_states.pop(self.entity_id, None)

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
        await self.restore_entity()
        template.attach(self.hass, self._config)
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._process_data()

    def restore_attributes(self, last_state: State) -> None:
        """Restore attributes."""
        for conf_key, attr in CONF_TO_ATTRIBUTE.items():
            if conf_key not in self._config or attr not in last_state.attributes:
                continue
            self._rendered[conf_key] = last_state.attributes[attr]

        if CONF_ATTRIBUTES in self._config:
            extra_state_attributes = {}
            for attr in self._config[CONF_ATTRIBUTES]:
                if attr not in last_state.attributes:
                    continue
                extra_state_attributes[attr] = last_state.attributes[attr]
            self._rendered[CONF_ATTRIBUTES] = extra_state_attributes

    async def restore_entity(
        self,
    ) -> tuple[State | None, dict[str, Any] | None]:
        """Restore the entity."""

        if not self.restore:
            return None, None

        if (last_sensor_state := await self.async_get_last_state()) is None:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "No state found to restore for entity %s", self.entity_id
            )
            return None, None

        # Restore all attributes.
        logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
            "Restoring entity %s", self.entity_id
        )
        self.restore_attributes(last_sensor_state)

        if (last_sensor_data := await self.async_get_last_rendered_data()) is None:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "No extra data found to restore for entity %s", self.entity_id
            )
            return last_sensor_state, None

        for attribute in self._extra_save_rendered:
            try:
                value = last_sensor_data[attribute]
            except KeyError:
                logging.getLogger(
                    f"{__package__}.{self.entity_id.split('.')[0]}"
                ).debug(
                    "Did not retrieve value for rendered attribute %s for entity %s",
                    attribute,
                    self.entity_id,
                )
                continue

            self._rendered[attribute] = value
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "Restored rendered attribute %s with value %s for entity %s",
                attribute,
                value,
                self.entity_id,
            )

        for attribute in self._extra_save_data:
            try:
                value = last_sensor_data[attribute]
            except KeyError:
                logging.getLogger(
                    f"{__package__}.{self.entity_id.split('.')[0]}"
                ).debug(
                    "Did not retrieve value for attribute %s for entity %s",
                    attribute,
                    self.entity_id,
                )
                continue

            setattr(self, attribute, value)
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "Restored additional attribute %s with value %s for entity %s",
                attribute,
                value,
                self.entity_id,
            )

        self.async_write_ha_state()

        return last_sensor_state, last_sensor_data

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

    def async_write_ha_state(self) -> None:
        """Write state to state machine.

        Disable saving state and re-enable again after writing state.
        If there is any uncaught error due to faulty attribute we thus
        ensure that this faulty attribute will not be saved.
        """

        try:
            self._save_extra_data = False
            super().async_write_ha_state()
            self._save_extra_data = True
        except (TypeError, ValueError) as exc:
            # Writing state resulted in an issue. Stop storing states for now.
            self._save_extra_data = False
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").error(
                "Writing state to state machine for entity %s results in exception: %s",
                self.entity_id,
                exc,
            )

    @property
    def extra_restore_state_data(self) -> TriggerExtraStoredData | None:
        """Return sensor specific state data to be restored."""
        return TriggerExtraStoredData(
            self,
            self._rendered,
            self._config.get(CONF_ATTRIBUTES, {}),
            self._extra_save_data,
        )

    async def async_get_last_rendered_data(self) -> dict[str, Any] | None:
        """Restore native_value and native_unit_of_measurement."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return TriggerExtraStoredData(self, {}, {}, []).from_dict(
            restored_last_extra_data.as_dict()
        )


@dataclass
class TriggerExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    trigger_entity: TriggerEntity
    rendered_values: dict[str, Any]
    attributes: dict
    extra_save_data: list

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the sensor data."""

        if not self.trigger_entity.save_extra_data:
            # Only store not to restore data
            logging.getLogger(f"{__package__}").debug(
                "Storing of data disabled for entity %s",
                self.trigger_entity.entity_id,
            )
            return {}

        dict_values: dict[str, Any] = {}

        for key, value in self.rendered_values.items():
            if key in self.attributes:
                continue

            value = TemplateJSONEncoder().default(value)
            logging.getLogger(f"{__package__}").info(
                "Storing attribute %s with value %s for entity %s",
                key,
                value,
                self.trigger_entity.entity_id,
            )
            dict_values.update({key: value})

        for attribute in self.extra_save_data:
            try:
                value = TemplateJSONEncoder().default(
                    getattr(self.trigger_entity, attribute)
                )
            except AttributeError:
                continue

            logging.getLogger(f"{__package__}").info(
                "Storing additional attribute %s with value %s for entity %s",
                attribute,
                value,
                self.trigger_entity.entity_id,
            )
            dict_values.update({attribute: value})

        return dict_values

    def from_dict(self, restored: dict[str, Any]) -> dict[str, Any]:
        """Initialize a stored sensor state from a dict."""
        dict_values: dict[str, Any] = {}

        for key, value in restored.items():
            value = TemplateJSONDecoder().default(value)
            logging.getLogger(f"{__package__}").info(
                "Retrieved attribute %s with value %s for entity %s",
                key,
                value,
                self.trigger_entity.entity_id,
            )
            dict_values.update({key: value})

        return dict_values
