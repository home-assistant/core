"""Offer Z-Wave JS event listening automation trigger."""

from __future__ import annotations

from collections.abc import Callable
import functools

from pydantic import ValidationError
import voluptuous as vol
from zwave_js_server.model.controller import CONTROLLER_EVENT_MODEL_MAP
from zwave_js_server.model.driver import DRIVER_EVENT_MODEL_MAP, Driver
from zwave_js_server.model.node import NODE_EVENT_MODEL_MAP

from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
)
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import Trigger, TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from ..const import (
    ATTR_EVENT,
    ATTR_EVENT_DATA,
    ATTR_EVENT_SOURCE,
    ATTR_NODE_ID,
    ATTR_PARTIAL_DICT_MATCH,
    DOMAIN,
)
from ..helpers import (
    async_get_nodes_from_targets,
    get_device_id,
    get_home_and_node_id_from_device_entry,
)
from .trigger_helpers import async_bypass_dynamic_config_validation

# Relative platform type should be <SUBMODULE_NAME>
RELATIVE_PLATFORM_TYPE = f"{__name__.rsplit('.', maxsplit=1)[-1]}"

# Platform type should be <DOMAIN>.<SUBMODULE_NAME>
PLATFORM_TYPE = f"{DOMAIN}.{RELATIVE_PLATFORM_TYPE}"


def validate_non_node_event_source(obj: dict) -> dict:
    """Validate that a trigger for a non node event source has a config entry."""
    if obj[ATTR_EVENT_SOURCE] != "node" and ATTR_CONFIG_ENTRY_ID in obj:
        return obj
    raise vol.Invalid(f"Non node event triggers must contain {ATTR_CONFIG_ENTRY_ID}.")


def validate_event_name(obj: dict) -> dict:
    """Validate that a trigger has a valid event name."""
    event_source = obj[ATTR_EVENT_SOURCE]
    event_name = obj[ATTR_EVENT]
    # the keys to the event source's model map are the event names
    if event_source == "controller":
        vol.In(CONTROLLER_EVENT_MODEL_MAP)(event_name)
    elif event_source == "driver":
        vol.In(DRIVER_EVENT_MODEL_MAP)(event_name)
    else:
        vol.In(NODE_EVENT_MODEL_MAP)(event_name)
    return obj


def validate_event_data(obj: dict) -> dict:
    """Validate that a trigger has a valid event data."""
    # Return if there's no event data to validate
    if ATTR_EVENT_DATA not in obj:
        return obj

    event_source: str = obj[ATTR_EVENT_SOURCE]
    event_name: str = obj[ATTR_EVENT]
    event_data: dict = obj[ATTR_EVENT_DATA]
    try:
        if event_source == "controller":
            CONTROLLER_EVENT_MODEL_MAP[event_name](**event_data)
        elif event_source == "driver":
            DRIVER_EVENT_MODEL_MAP[event_name](**event_data)
        else:
            NODE_EVENT_MODEL_MAP[event_name](**event_data)
    except ValidationError as exc:
        # Filter out required field errors if keys can be missing, and if there are
        # still errors, raise an exception
        if [error for error in exc.errors() if error["type"] != "missing"]:
            raise vol.MultipleInvalid from exc
    return obj


TRIGGER_SCHEMA = vol.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_PLATFORM): PLATFORM_TYPE,
            vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
            vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Required(ATTR_EVENT_SOURCE): vol.In(["controller", "driver", "node"]),
            vol.Required(ATTR_EVENT): cv.string,
            vol.Optional(ATTR_EVENT_DATA): dict,
            vol.Optional(ATTR_PARTIAL_DICT_MATCH, default=False): bool,
        },
    ),
    validate_event_name,
    validate_event_data,
    vol.Any(
        validate_non_node_event_source,
        cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
    ),
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    if ATTR_CONFIG_ENTRY_ID in config:
        entry_id = config[ATTR_CONFIG_ENTRY_ID]
        if hass.config_entries.async_get_entry(entry_id) is None:
            raise vol.Invalid(f"Config entry '{entry_id}' not found")

    if async_bypass_dynamic_config_validation(hass, config):
        return config

    if config[ATTR_EVENT_SOURCE] == "node" and not async_get_nodes_from_targets(
        hass, config
    ):
        raise vol.Invalid(
            f"No nodes found for given {ATTR_DEVICE_ID}s or {ATTR_ENTITY_ID}s."
        )

    return config


class EventTrigger(Trigger):
    """Z-Wave JS event trigger."""

    _platform_type = PLATFORM_TYPE

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> None:
        """Initialize trigger."""
        self._config = config
        self._hass = hass
        self._event_source = config[ATTR_EVENT_SOURCE]
        self._event_name = config[ATTR_EVENT]
        self._event_data_filter = config.get(ATTR_EVENT_DATA, {})

        self._unsubs: list[Callable] = []
        self._job = HassJob(action)

        self._trigger_data = trigger_info["trigger_data"]

    @classmethod
    async def async_validate_trigger_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return await async_validate_trigger_config(hass, config)

    @classmethod
    async def async_attach_trigger(
        cls,
        hass: HomeAssistant,
        config: ConfigType,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        dev_reg = dr.async_get(hass)
        if config[ATTR_EVENT_SOURCE] == "node" and not async_get_nodes_from_targets(
            hass, config, dev_reg=dev_reg
        ):
            raise ValueError(
                f"No nodes found for given {ATTR_DEVICE_ID}s or {ATTR_ENTITY_ID}s."
            )

        trigger = cls(hass, config, action, trigger_info)
        trigger._create_zwave_listeners()
        return trigger._async_remove

    @callback
    def _async_on_event(
        self, event_data: dict, device: dr.DeviceEntry | None = None
    ) -> None:
        """Handle event."""
        for key, val in self._event_data_filter.items():
            if key not in event_data:
                return
            if (
                self._config[ATTR_PARTIAL_DICT_MATCH]
                and isinstance(event_data[key], dict)
                and isinstance(self._event_data_filter[key], dict)
            ):
                for key2, val2 in self._event_data_filter[key].items():
                    if key2 not in event_data[key] or event_data[key][key2] != val2:
                        return
                continue
            if event_data[key] != val:
                return

        payload = {
            **self._trigger_data,
            CONF_PLATFORM: self._platform_type,
            ATTR_EVENT_SOURCE: self._event_source,
            ATTR_EVENT: self._event_name,
            ATTR_EVENT_DATA: event_data,
        }

        primary_desc = (
            f"Z-Wave JS '{self._event_source}' event '{self._event_name}' was emitted"
        )

        if device:
            device_name = device.name_by_user or device.name
            payload[ATTR_DEVICE_ID] = device.id
            home_and_node_id = get_home_and_node_id_from_device_entry(device)
            assert home_and_node_id
            payload[ATTR_NODE_ID] = home_and_node_id[1]
            payload["description"] = f"{primary_desc} on {device_name}"
        else:
            payload["description"] = primary_desc

        payload["description"] = (
            f"{payload['description']} with event data: {event_data}"
        )

        self._hass.async_run_hass_job(self._job, {"trigger": payload})

    @callback
    def _async_remove(self) -> None:
        """Remove state listeners async."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _create_zwave_listeners(self) -> None:
        """Create Z-Wave JS listeners."""
        self._async_remove()
        # Nodes list can come from different drivers and we will need to listen to
        # server connections for all of them.
        drivers: set[Driver] = set()
        dev_reg = dr.async_get(self._hass)
        if not (
            nodes := async_get_nodes_from_targets(
                self._hass, self._config, dev_reg=dev_reg
            )
        ):
            entry_id = self._config[ATTR_CONFIG_ENTRY_ID]
            entry = self._hass.config_entries.async_get_entry(entry_id)
            assert entry
            client: Client = entry.runtime_data[DATA_CLIENT]
            driver = client.driver
            assert driver
            drivers.add(driver)
            if self._event_source == "controller":
                self._unsubs.append(
                    driver.controller.on(self._event_name, self._async_on_event)
                )
            else:
                self._unsubs.append(driver.on(self._event_name, self._async_on_event))

        for node in nodes:
            driver = node.client.driver
            assert driver is not None  # The node comes from the driver.
            drivers.add(driver)
            device_identifier = get_device_id(driver, node)
            device = dev_reg.async_get_device(identifiers={device_identifier})
            assert device
            # We need to store the device for the callback
            self._unsubs.append(
                node.on(
                    self._event_name,
                    functools.partial(self._async_on_event, device=device),
                )
            )
        self._unsubs.extend(
            async_dispatcher_connect(
                self._hass,
                f"{DOMAIN}_{driver.controller.home_id}_connected_to_server",
                self._create_zwave_listeners,
            )
            for driver in drivers
        )
