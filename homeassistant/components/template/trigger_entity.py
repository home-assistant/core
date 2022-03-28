"""Trigger entity."""
from __future__ import annotations

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
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    TriggerUpdateCoordinator,
    convert_attribute_from_string,
    convert_attribute_to_string,
)
from .const import CONF_ATTRIBUTES, CONF_AVAILABILITY, CONF_PICTURE

CONF_TO_ATTRIBUTE = {
    CONF_ICON: ATTR_ICON,
    CONF_NAME: ATTR_FRIENDLY_NAME,
    CONF_PICTURE: ATTR_ENTITY_PICTURE,
}


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

        if self.extra_template_keys is not None:
            self._to_render_simple.extend(self.extra_template_keys)

        if self.extra_template_keys_complex is not None:
            self._to_render_complex.extend(self.extra_template_keys_complex)

        # We make a copy so our initial render is 'unknown' and not 'unavailable'
        self._rendered = dict(self._static_rendered)
        self._parse_result = {CONF_AVAILABILITY}

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

    async def async_added_to_hass(self) -> None:
        """Handle being added to Home Assistant."""
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

    def __init__(self, *args, **kwargs) -> None:
        """Template Restore Entity init."""
        super().__init__(*args, **kwargs)
        self._restore: bool = False
        self._save_state: bool = True
        self._additional_data: list[str] = []

    @property
    def restore(self) -> bool:
        """Retrieve restore."""
        return self._restore or False

    @restore.setter
    def restore(self, restore: bool) -> None:
        """Set restore."""
        self._restore = restore

    @property
    def save_state(self) -> bool:
        """Retrieve save state."""
        return self._save_state if hasattr(self, "_save_state") else True

    @property
    def additional_data(self) -> list[str]:
        """Return additional data list."""
        return self._additional_data or []

    def add_additional_data(self, attribute: str) -> None:
        """Add attribute to additional data list."""
        if not hasattr(self, "_additional_data"):
            self._additional_data = []

        self._additional_data.append(attribute)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._process_data()
        self._save_state = False
        self.async_write_ha_state()
        self._save_state = True

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

        if (last_sensor_data := await self.async_get_last_rendered_data()) is None:
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "No extra data found to restore for entity %s", self.entity_id
            )
            return last_sensor_state, None

        # Restore all attributes.
        logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
            "Restoring entity %s", self.entity_id
        )

        def restore_rendered(self, last_sensor_data: dict[str, Any], key: str) -> None:
            """Update self._rendered with stored value."""

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
                return

            self._rendered[key] = value
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").debug(
                "Restored additional attribute %s with value %s for entity %s",
                key,
                value,
                self.entity_id,
            )

        for key in self._to_render_simple:
            restore_rendered(self, last_sensor_data, key)

        for key in self._to_render_complex:
            restore_rendered(self, last_sensor_data, key)

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

        for attribute in self.additional_data:
            try:
                value = last_sensor_data[attribute]
            except KeyError:
                logging.getLogger(
                    f"{__package__}.{self.entity_id.split('.')[0]}"
                ).debug(
                    "Did not retrieve value for additional attribute %s for entity %s",
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

        try:
            self.async_write_ha_state()
        except (TypeError, ValueError) as exc:
            # Writing state resulted in an issue. Stop storing states for now.
            self._save_state = False
            logging.getLogger(f"{__package__}.{self.entity_id.split('.')[0]}").error(
                "Restored state for entity %s results in exception: %s",
                self.entity_id,
                exc,
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
            TriggerExtraStoredData(self, self._rendered)
            if self.restore
            else TriggerExtraStoredData(self, None)
        )

    async def async_get_last_rendered_data(self) -> dict[str, Any] | None:
        """Restore native_value and native_unit_of_measurement."""
        if not self.restore:
            return None

        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return TriggerExtraStoredData(self, None).from_dict(
            restored_last_extra_data.as_dict()
        )


@dataclass
class TriggerExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    trigger_entity: TriggerRestoreEntity
    rendered_values: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the sensor data."""

        if not self.trigger_entity.save_state:
            # Only store not to restore data
            logging.getLogger(f"{__package__}").debug(
                "Storing of data disabled for entity %s",
                self.trigger_entity.entity_id,
            )
            return {}

        dict_values: dict[str, Any] = {}

        if self.rendered_values is not None:
            for key, value in self.rendered_values.items():
                value = convert_attribute_to_string(value)
                logging.getLogger(f"{__package__}").info(
                    "Storing attribute %s with value %s for entity %s",
                    key,
                    value,
                    self.trigger_entity.entity_id,
                )
                dict_values.update({key: value})

        if self.trigger_entity is not None:
            for attribute in self.trigger_entity.additional_data:
                try:
                    value = convert_attribute_to_string(
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
            value = convert_attribute_from_string(value)
            logging.getLogger(f"{__package__}").info(
                "Retrieved attribute %s with value %s for entity %s",
                key,
                value,
                self.trigger_entity.entity_id,
            )
            dict_values.update({key: value})

        return dict_values
