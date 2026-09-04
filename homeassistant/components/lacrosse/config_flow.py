"""Config flow for the LaCrosse integration."""

import logging
from typing import Any, Final, override
from uuid import uuid4

import voluptuous as vol

from homeassistant.components import usb
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BATTERY,
    CONF_BAUD,
    CONF_DATARATE,
    CONF_EXPIRE_AFTER,
    CONF_FREQUENCY,
    CONF_HUMIDITY,
    CONF_JEELINK_LED,
    CONF_NEW_ID,
    CONF_TEMPERATURE,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
    DEFAULT_BAUD,
    DEFAULT_DEVICE,
    DOMAIN,
    LaCrosseSensorType,
)

_LOGGER = logging.getLogger(__name__)

RECEIVER_OPTION_KEYS: Final = (
    CONF_DATARATE,
    CONF_FREQUENCY,
    CONF_JEELINK_LED,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
)

STEP_SENSOR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_TEMPERATURE, default=True): cv.boolean,
        vol.Required(CONF_HUMIDITY, default=False): cv.boolean,
        vol.Required(CONF_BATTERY, default=False): cv.boolean,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
    }
)

MIN_REQUIRED_SENSOR_TYPES = LaCrosseSensorType.TEMPERATURE | LaCrosseSensorType.HUMIDITY

EMPTY_VALUES: Final = (None, "")


async def _async_free_usb_ports(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Return the USB serial ports not already claimed by another integration.

    The device VID/PID can't be matched for USB discovery since most users rely
    on a custom made adapter, so free USB ports are offered as a select instead.
    """
    ports = [
        port
        for port in await usb.async_scan_serial_ports(hass)
        if isinstance(port, usb.USBDevice)
    ]
    consumers = await usb.async_get_serial_port_consumers(hass, ports)
    return [
        SelectOptionDict(
            value=port.device,
            label=usb.human_readable_device_name(
                port.device,
                port.serial_number,
                port.manufacturer,
                port.description,
                port.vid,
                port.pid,
            ),
        )
        for port in ports
        if not any(consumer.active for consumer in consumers.get(port.device, []))
    ]


def _receiver_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return receiver config from user input, dropping empty optional values."""
    data = {
        CONF_DEVICE: user_input[CONF_DEVICE],
        CONF_BAUD: user_input[CONF_BAUD],
    }
    for key in RECEIVER_OPTION_KEYS:
        if (value := user_input.get(key)) not in EMPTY_VALUES:
            data[key] = value
    return data


def _step_receiver_data_schema(
    ports: list[SelectOptionDict], defaults: dict[str, Any] | None = None
) -> vol.Schema:
    """Return the schema for the receiver configuration step."""
    defaults = defaults or {}
    optional_fields: dict[Any, Any] = {}
    for key in RECEIVER_OPTION_KEYS:
        marker = vol.Optional(key)
        if (suggested_value := defaults.get(key)) is not None:
            marker = vol.Optional(key, description={"suggested_value": suggested_value})
        optional_fields[marker] = vol.Any(
            cv.boolean if key == CONF_JEELINK_LED else cv.positive_int,
            *EMPTY_VALUES,
        )

    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE, default=defaults.get(CONF_DEVICE, DEFAULT_DEVICE)
            ): SelectSelector(
                SelectSelectorConfig(options=ports, custom_value=True, sort=True)
            ),
            vol.Required(
                CONF_BAUD, default=defaults.get(CONF_BAUD, DEFAULT_BAUD)
            ): cv.positive_int,
            **optional_fields,
        }
    )


def _sensor_select_options(
    sensors: dict[str, dict[str, Any]],
) -> list[SelectOptionDict]:
    """Return sorted select options for sensors, labeled with their friendly name."""
    options = {
        str(sensor[CONF_ID]): sensor.get(CONF_FRIENDLY_NAME, sensor[CONF_ID])
        for sensor in sensors.values()
    }
    return [
        SelectOptionDict(
            value=sensor_id,
            label=f"{name} ({sensor_id})" if name else sensor_id,
        )
        for sensor_id, name in sorted(options.items(), key=lambda item: int(item[0]))
    ]


class LaCrosseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LaCrosse."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._sensors: dict[str, dict[str, Any]] = {}
        self._update_sensor_id: int | None = None

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml (sensor platform)."""
        _LOGGER.warning(
            "Importing LaCrosse from YAML is deprecated and will be removed"
        )
        entry_input: dict[str, Any] = {
            CONF_DEVICE: import_config[CONF_DEVICE],
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
            sensor_type = LaCrosseSensorType[sensor_input[CONF_TYPE].upper()]
            sensor_id = sensor_type.sensor_key(sensor_input[CONF_ID])
            sensors[sensor_id] = sensor_input
        entry_input[CONF_SENSORS] = sensors

        self._async_abort_entries_match({CONF_DEVICE: entry_input[CONF_DEVICE]})
        return self.async_create_entry(title=entry_input[CONF_DEVICE], data=entry_input)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial receiver configuration step."""
        if user_input is not None:
            user_input[CONF_DEVICE] = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input[CONF_DEVICE]
            )
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            self._data = _receiver_data(user_input)
            return await self.async_step_add_sensor()

        ports = await _async_free_usb_ports(self.hass)
        return self.async_show_form(
            step_id="user", data_schema=_step_receiver_data_schema(ports)
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the reconfiguration options of an existing receiver."""
        self._data = dict(self._get_reconfigure_entry().data)
        self._sensors = dict(self._data.pop(CONF_SENSORS, {}))
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "update_receiver",
                "add_sensor",
                "update_sensor",
                "remove_sensor",
            ],
        )

    async def async_step_update_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the receiver configuration."""
        if user_input is not None:
            old_receiver = self._data[CONF_DEVICE]
            user_input[CONF_DEVICE] = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_input[CONF_DEVICE]
            )
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            self._data = _receiver_data(user_input)
            self._async_update_receiver_devices(old_receiver, user_input[CONF_DEVICE])
            return await self.async_step_finish()

        ports = await _async_free_usb_ports(self.hass)
        return self.async_show_form(
            step_id="update_receiver",
            data_schema=_step_receiver_data_schema(ports, self._data),
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

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a sensor received by the configured receiver."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = LaCrosseSensorType(0)
            for sensor_type in LaCrosseSensorType:
                if user_input.pop(sensor_type.key):
                    selected |= sensor_type

            sensor_id = user_input[CONF_ID]
            keys = {
                sensor_type: sensor_type.sensor_key(sensor_id)
                for sensor_type in LaCrosseSensorType
                if sensor_type & selected
            }
            configured_types = {
                (sensor[CONF_ID], sensor[CONF_TYPE])
                for sensor in self._sensors.values()
            }

            if not selected & MIN_REQUIRED_SENSOR_TYPES:
                errors["base"] = "value_type_required"
            elif any(
                (sensor_id, sensor_type.key) in configured_types for sensor_type in keys
            ):
                errors["base"] = "sensor_already_configured"
            else:
                for sensor_type, key in keys.items():
                    self._sensors[key] = {
                        **user_input,
                        CONF_TYPE: sensor_type.key,
                        CONF_UNIQUE_ID: uuid4().hex,
                    }
                return await self.async_step_add_sensor_or_finish()

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=STEP_SENSOR_DATA_SCHEMA,
            errors=errors or None,
        )

    async def async_step_add_sensor_or_finish(self) -> ConfigFlowResult:
        """Offer to add another sensor or complete the flow."""
        return self.async_show_menu(
            step_id="add_sensor_or_finish", menu_options=["add_sensor", "finish"]
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update an entry using the configured receiver and sensors."""
        data = {**self._data, CONF_SENSORS: self._sensors}
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), title=self._data[CONF_DEVICE], data=data
            )
        return self.async_create_entry(title=self._data[CONF_DEVICE], data=data)

    async def async_step_update_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the ID and name of a sensor."""
        if self._update_sensor_id is None:
            if user_input is not None:
                self._update_sensor_id = int(user_input[CONF_ID])
                return await self.async_step_update_sensor_details()

            sensor_options = _sensor_select_options(self._sensors)
            return self.async_show_form(
                step_id="update_sensor",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ID): SelectSelector(
                            SelectSelectorConfig(options=sensor_options)
                        )
                    }
                ),
            )

        return await self.async_step_update_sensor_details(user_input)

    async def async_step_update_sensor_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update the selected sensor's ID and name."""
        errors: dict[str, str] = {}

        sensor_by_id = {sensor[CONF_ID]: sensor for sensor in self._sensors.values()}
        sensor_id = self._update_sensor_id
        assert sensor_id is not None
        sensor = sensor_by_id[sensor_id]

        if user_input is not None:
            old_id = sensor_id
            new_id = user_input[CONF_NEW_ID]
            new_name = user_input.get(CONF_FRIENDLY_NAME)

            if any(
                sensor[CONF_ID] == new_id
                for sensor in self._sensors.values()
                if sensor[CONF_ID] != old_id
            ):
                errors["base"] = "sensor_already_configured"
            else:
                sensors: dict[str, dict[str, Any]] = {}
                for key, sensor in self._sensors.items():
                    if sensor[CONF_ID] != old_id:
                        sensors[key] = sensor
                        continue
                    sensor_type = LaCrosseSensorType[sensor[CONF_TYPE].upper()]
                    updated_sensor = {
                        **sensor,
                        CONF_ID: new_id,
                    }
                    if new_name:
                        updated_sensor[CONF_FRIENDLY_NAME] = new_name
                    else:
                        updated_sensor.pop(CONF_FRIENDLY_NAME, None)
                    sensors[sensor_type.sensor_key(new_id)] = updated_sensor
                self._sensors = sensors
                self._async_update_device(old_id, new_id, new_name)
                return await self.async_step_finish()

        detail_schema: dict[Any, Any] = {
            vol.Required(CONF_NEW_ID, default=sensor_id): cv.positive_int,
        }
        if friendly_name := sensor.get(CONF_FRIENDLY_NAME):
            detail_schema[
                vol.Optional(
                    CONF_FRIENDLY_NAME, description={"suggested_value": friendly_name}
                )
            ] = cv.string
        else:
            detail_schema[vol.Optional(CONF_FRIENDLY_NAME)] = cv.string

        return self.async_show_form(
            step_id="update_sensor",
            data_schema=vol.Schema(detail_schema),
            errors=errors or None,
        )

    def _async_update_device(self, old_id: int, new_id: int, name: str | None) -> None:
        """Update the device of a sensor to keep its customizations."""
        receiver = self._data[CONF_DEVICE]
        device_registry = dr.async_get(self.hass)
        if device := device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{receiver}_{old_id}"), self._get_reconfigure_entry().entry_id
        ):
            device_registry.async_update_device(
                device.id,
                new_identifiers={(DOMAIN, f"{receiver}_{new_id}")},
                name=name or None,
            )

    async def async_step_remove_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a sensor and its device from the receiver."""
        if user_input is not None:
            sensor_id = int(user_input[CONF_ID])
            self._sensors = {
                key: sensor
                for key, sensor in self._sensors.items()
                if sensor[CONF_ID] != sensor_id
            }
            self._async_remove_device(sensor_id)
            return await self.async_step_finish()

        sensor_options = _sensor_select_options(self._sensors)
        return self.async_show_form(
            step_id="remove_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): SelectSelector(
                        SelectSelectorConfig(options=sensor_options)
                    ),
                }
            ),
        )

    def _async_remove_device(self, sensor_id: int) -> None:
        """Remove the device registry entry of a removed sensor."""
        receiver = self._data[CONF_DEVICE]
        device_registry = dr.async_get(self.hass)
        if device := device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{receiver}_{sensor_id}"), self._get_reconfigure_entry().entry_id
        ):
            device_registry.async_remove_device(device.id)
