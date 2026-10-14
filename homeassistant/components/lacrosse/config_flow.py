"""Config flow for the LaCrosse integration."""

from collections.abc import Iterable, Mapping
import logging
from typing import Any, Final, override
from uuid import uuid4

import probatio
import pylacrosse
from serial import SerialException

from homeassistant.components import usb
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_FRIENDLY_NAME,
    CONF_ID,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import SerialPortSelector
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import ensure_unique_string

from .const import (
    CONF_BATTERY,
    CONF_BAUD,
    CONF_DATARATE,
    CONF_EXPIRE_AFTER,
    CONF_FREQUENCY,
    CONF_HUMIDITY,
    CONF_JEELINK_LED,
    CONF_TEMPERATURE,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
    DEFAULT_BAUD,
    DOMAIN,
    LaCrosseSensorType,
    sensor_entity_key,
)

_LOGGER = logging.getLogger(__name__)

RECEIVER_OPTION_KEYS: Final = (
    CONF_DATARATE,
    CONF_FREQUENCY,
    CONF_JEELINK_LED,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
)

STEP_SENSOR_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ID): cv.positive_int,
        probatio.Required(CONF_TEMPERATURE, default=True): cv.boolean,
        probatio.Required(CONF_HUMIDITY, default=False): cv.boolean,
        probatio.Required(CONF_BATTERY, default=False): cv.boolean,
        probatio.Optional(CONF_FRIENDLY_NAME): cv.string,
        probatio.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
    }
)

MIN_REQUIRED_SENSOR_TYPES = LaCrosseSensorType.TEMPERATURE | LaCrosseSensorType.HUMIDITY

EMPTY_VALUES: Final = (None, "")


def _test_connection(data: dict[str, Any]) -> None:
    """Test that the receiver can be opened."""
    receiver = pylacrosse.LaCrosse(data[CONF_DEVICE], data[CONF_BAUD])
    receiver.open()
    receiver.close()


async def _async_test_connection(
    hass: HomeAssistant, data: dict[str, Any]
) -> str | None:
    """Test the receiver and return a form error when it cannot be opened."""
    try:
        await hass.async_add_executor_job(_test_connection, data)
    except SerialException:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error while testing the receiver")
        return "unknown"
    return None


def _receiver_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return receiver config from user input, dropping empty optional values."""
    data = {
        CONF_DEVICE: user_input[CONF_DEVICE],
        CONF_BAUD: user_input[CONF_BAUD],
    }
    for key in RECEIVER_OPTION_KEYS:
        if (value := user_input.get(key)) not in EMPTY_VALUES:
            data[key] = round(value * 1000) if key == CONF_FREQUENCY else value
    return data


def _step_receiver_data_schema(
    defaults: dict[str, Any] | None = None,
) -> probatio.Schema:
    """Return the schema for the receiver configuration step."""
    defaults = defaults or {}
    optional_fields: dict[Any, Any] = {}
    for key in RECEIVER_OPTION_KEYS:
        marker = probatio.Optional(key)
        if (suggested_value := defaults.get(key)) is not None:
            if key == CONF_FREQUENCY:
                suggested_value /= 1000
            marker = probatio.Optional(
                key, description={"suggested_value": suggested_value}
            )
        optional_fields[marker] = probatio.Any(
            cv.boolean
            if key == CONF_JEELINK_LED
            else cv.positive_float
            if key == CONF_FREQUENCY
            else cv.positive_int,
            *EMPTY_VALUES,
        )

    return probatio.Schema(
        {
            probatio.Required(
                CONF_DEVICE,
                description={"suggested_value": defaults[CONF_DEVICE]}
                if CONF_DEVICE in defaults
                else {},
            ): SerialPortSelector(),
            probatio.Required(
                CONF_BAUD, default=defaults.get(CONF_BAUD, DEFAULT_BAUD)
            ): cv.positive_int,
            **optional_fields,
        }
    )


def sensor_subentries(
    sensors: Mapping[str, dict[str, Any]],
) -> list[ConfigSubentryData]:
    """Group sensor entities into physical sensor subentries."""
    grouped: dict[int, dict[str, dict[str, Any]]] = {}
    for key, sensor in sensors.items():
        grouped.setdefault(sensor[CONF_ID], {})[key] = sensor
    return [
        ConfigSubentryData(
            data={CONF_SENSORS: sensor_data},
            subentry_type="sensor",
            title=next(iter(sensor_data.values())).get(CONF_FRIENDLY_NAME)
            or f"LaCrosse sensor {sensor_id}",
            unique_id=str(sensor_id),
        )
        for sensor_id, sensor_data in grouped.items()
    ]


def _sensor_id_is_configured(
    sensor_id: int, sensors: Iterable[Mapping[str, Any]]
) -> bool:
    """Check if a sensor ID is already configured on the receiver."""
    return any(sensor[CONF_ID] == sensor_id for sensor in sensors)


def _selected_sensor_types(
    user_input: Mapping[str, Any],
) -> list[LaCrosseSensorType]:
    """Return the selected sensor types from user input."""
    return [
        sensor_type for sensor_type in LaCrosseSensorType if user_input[sensor_type.key]
    ]


def _sensor_input_error(
    sensor_id: int,
    selected: Iterable[LaCrosseSensorType],
    configured_sensors: Iterable[Mapping[str, Any]],
) -> str | None:
    """Return a validation error for the selected sensor types and ID."""
    if not any(sensor_type & MIN_REQUIRED_SENSOR_TYPES for sensor_type in selected):
        return "value_type_required"
    if _sensor_id_is_configured(sensor_id, configured_sensors):
        return "sensor_already_configured"
    return None


def _sensor_details(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Return sensor details without the selected type flags."""
    return {
        key: value
        for key, value in user_input.items()
        if key not in {sensor_type.key for sensor_type in LaCrosseSensorType}
    }


class LaCrosseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LaCrosse."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the supported sensor subentry flow."""
        return {"sensor": LaCrosseSensorSubentryFlow}

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._sensors: dict[str, dict[str, Any]] = {}

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml (sensor platform)."""
        _LOGGER.warning(
            "Importing LaCrosse from YAML is deprecated and will be removed"
        )
        resolved_device = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, import_config.get(CONF_DEVICE, "/dev/ttyUSB0")
        )
        entry_input: dict[str, Any] = {
            CONF_DEVICE: resolved_device,
            CONF_BAUD: import_config[CONF_BAUD],
            CONF_DATARATE: import_config.get(CONF_DATARATE),
            CONF_FREQUENCY: import_config.get(CONF_FREQUENCY),
            CONF_JEELINK_LED: import_config.get(CONF_JEELINK_LED),
            CONF_TOGGLE_INTERVAL: import_config.get(CONF_TOGGLE_INTERVAL),
            CONF_TOGGLE_MASK: import_config.get(CONF_TOGGLE_MASK),
        }
        sensors: dict[str, dict[str, Any]] = {}
        for slug, sensor_config in import_config.get(CONF_SENSORS, {}).items():
            sensor_input = dict(sensor_config)
            sensor_input[CONF_FRIENDLY_NAME] = sensor_input.pop(CONF_NAME, slug)
            sensor_input[CONF_UNIQUE_ID] = uuid4().hex
            sensors[slug] = sensor_input

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2027.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "LaCrosse",
            },
        )

        self._async_abort_entries_match({CONF_DEVICE: entry_input[CONF_DEVICE]})
        return self.async_create_entry(
            title=entry_input[CONF_DEVICE],
            data=entry_input,
            subentries=sensor_subentries(sensors),
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial receiver configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_DEVICE] = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input[CONF_DEVICE]
            )
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            data = _receiver_data(user_input)
            if error := await _async_test_connection(self.hass, data):
                errors["base"] = error
            else:
                self._data = data
                return self.async_create_entry(
                    title=self._data[CONF_DEVICE], data=self._data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_step_receiver_data_schema(),
            errors=errors or None,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the receiver configuration."""
        entry = self._get_reconfigure_entry()
        self._data = dict(entry.data)
        self._sensors = {
            key: sensor
            for subentry in entry.subentries.values()
            for key, sensor in subentry.data[CONF_SENSORS].items()
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            old_receiver = self._data[CONF_DEVICE]
            user_input[CONF_DEVICE] = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input[CONF_DEVICE]
            )
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            data = _receiver_data(user_input)
            unload_receiver = (
                old_receiver == data[CONF_DEVICE]
                and entry.state is ConfigEntryState.LOADED
            )
            if unload_receiver and not await self.hass.config_entries.async_unload(
                entry.entry_id
            ):
                errors["base"] = "unknown"
            elif error := await _async_test_connection(self.hass, data):
                errors["base"] = error
                if unload_receiver:
                    await self.hass.config_entries.async_reload(entry.entry_id)
            else:
                self._data = data
                self._async_update_receiver_devices(
                    old_receiver, user_input[CONF_DEVICE]
                )
                result = self.async_update_and_abort(
                    entry,
                    title=self._data[CONF_DEVICE],
                    data=self._data,
                )
                if entry.state is not ConfigEntryState.LOADED:
                    await self.hass.config_entries.async_reload(entry.entry_id)
                return result

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_step_receiver_data_schema(self._data),
            errors=errors or None,
        )

    def _async_update_receiver_devices(
        self, old_receiver: str, new_receiver: str
    ) -> None:
        """Update sensor device identifiers for a changed receiver."""
        if old_receiver == new_receiver:
            return

        device_registry = dr.async_get(self.hass)
        entry_id = self._get_reconfigure_entry().entry_id
        for sensor_id in {sensor[CONF_ID] for sensor in self._sensors.values()}:
            if device := device_registry.async_get_device_by_identifier(
                (DOMAIN, f"{old_receiver}_{sensor_id}"), entry_id
            ):
                device_registry.async_update_device(
                    device.id,
                    new_identifiers={(DOMAIN, f"{new_receiver}_{sensor_id}")},
                )


class LaCrosseSensorSubentryFlow(ConfigSubentryFlow):
    """Configure a physical sensor independently of its receiver."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a sensor to the selected receiver."""
        errors: dict[str, str] = {}
        if user_input is not None:
            sensor_id = user_input[CONF_ID]
            selected = _selected_sensor_types(user_input)
            configured_sensors = (
                sensor
                for subentry in self._get_entry().subentries.values()
                for sensor in subentry.data[CONF_SENSORS].values()
            )
            if error := _sensor_input_error(
                sensor_id,
                selected,
                configured_sensors,
            ):
                errors["base"] = error
            else:
                details = _sensor_details(user_input)
                sensors: dict[str, dict[str, Any]] = {}
                for sensor_type in selected:
                    key = ensure_unique_string(
                        sensor_entity_key(
                            sensor_id,
                            sensor_type,
                            user_input.get(CONF_FRIENDLY_NAME),
                        ),
                        (
                            key
                            for subentry in self._get_entry().subentries.values()
                            for key in subentry.data[CONF_SENSORS]
                        ),
                    )

                    sensors[key] = {
                        **details,
                        CONF_TYPE: sensor_type.key,
                        CONF_UNIQUE_ID: uuid4().hex,
                    }
                return self.async_create_entry(
                    title=user_input.get(CONF_FRIENDLY_NAME)
                    or f"LaCrosse sensor {sensor_id}",
                    unique_id=str(sensor_id),
                    data={CONF_SENSORS: sensors},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SENSOR_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Update a sensor with its current ID and types preselected."""
        entry = self._get_entry()
        reconfigure_subentry = self._get_reconfigure_subentry()
        sensors = reconfigure_subentry.data[CONF_SENSORS]
        sensor = next(iter(sensors.values()))
        errors: dict[str, str] = {}
        if user_input is not None:
            new_id = user_input[CONF_ID]
            selected = _selected_sensor_types(user_input)
            configured_sensors = (
                configured
                for other in entry.subentries.values()
                if other.subentry_id != reconfigure_subentry.subentry_id
                for configured in other.data[CONF_SENSORS].values()
            )
            if error := _sensor_input_error(
                new_id,
                selected,
                configured_sensors,
            ):
                errors["base"] = error
            else:
                by_type = {sensor[CONF_TYPE]: sensor for sensor in sensors.values()}
                details = _sensor_details(user_input)
                existing_keys = {
                    configured_key
                    for subentry in entry.subentries.values()
                    for configured_key, configured in subentry.data[
                        CONF_SENSORS
                    ].items()
                    if configured[CONF_ID] != sensor[CONF_ID]
                }
                updated: dict[str, dict[str, Any]] = {}
                for sensor_type in selected:
                    key = ensure_unique_string(
                        sensor_entity_key(
                            new_id,
                            sensor_type,
                            details.get(CONF_FRIENDLY_NAME),
                        ),
                        existing_keys,
                    )
                    updated[key] = {
                        **details,
                        CONF_TYPE: sensor_type.key,
                        CONF_UNIQUE_ID: by_type[sensor_type.key][CONF_UNIQUE_ID]
                        if sensor_type.key in by_type
                        else uuid4().hex,
                    }
                entity_registry = er.async_get(self.hass)
                removed_ids = {
                    sensor[CONF_UNIQUE_ID]
                    for sensor in sensors.values()
                    if sensor[CONF_TYPE]
                    not in {sensor_type.key for sensor_type in selected}
                }
                for entity in er.async_entries_for_config_entry(
                    entity_registry, entry.entry_id
                ):
                    if entity.unique_id in removed_ids:
                        entity_registry.async_remove(entity.entity_id)
                receiver = entry.data[CONF_DEVICE]
                device_registry = dr.async_get(self.hass)
                name = user_input.get(CONF_FRIENDLY_NAME)
                if device := device_registry.async_get_device_by_identifier(
                    (DOMAIN, f"{receiver}_{sensor[CONF_ID]}"), entry.entry_id
                ):
                    device_registry.async_update_device(
                        device.id,
                        new_identifiers={(DOMAIN, f"{receiver}_{new_id}")},
                        name=name or f"LaCrosse sensor {new_id}",
                        model=f"Sensor ID {new_id}",
                    )
                return self.async_update_and_abort(
                    entry,
                    reconfigure_subentry,
                    unique_id=str(new_id),
                    title=name or f"LaCrosse sensor {new_id}",
                    data={CONF_SENSORS: updated},
                )

        defaults = {
            **sensor,
            **{
                sensor_type.key: any(
                    configured[CONF_TYPE] == sensor_type.key
                    for configured in sensors.values()
                )
                for sensor_type in LaCrosseSensorType
            },
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_SENSOR_DATA_SCHEMA, defaults
            ),
            errors=errors,
        )
