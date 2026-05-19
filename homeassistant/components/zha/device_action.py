"""Provides device actions for ZHA devices."""

from typing import Any

import voluptuous as vol
from zha.exceptions import ZHAException
from zhaquirks.inovelli.types import AllLEDEffectType, SingleLEDEffectType
from zigpy.zcl.clusters.security import IasWd

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN
from .helpers import async_get_zha_device_proxy
from .websocket_api import SERVICE_WARNING_DEVICE_SQUAWK, SERVICE_WARNING_DEVICE_WARN

# mypy: disallow-any-generics

INOVELLI_CLUSTER_ID = 0xFC31

ACTION_SQUAWK = "squawk"
ACTION_WARN = "warn"
ATTR_DATA = "data"
ATTR_IEEE = "ieee"
CONF_ZHA_ACTION_TYPE = "zha_action_type"
ZHA_ACTION_TYPE_SERVICE_CALL = "service_call"
ZHA_ACTION_TYPE_CLUSTER_COMMAND = "cluster_command"
INOVELLI_ALL_LED_EFFECT = "issue_all_led_effect"
INOVELLI_INDIVIDUAL_LED_EFFECT = "issue_individual_led_effect"

DEFAULT_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): vol.In({ACTION_SQUAWK, ACTION_WARN}),
    }
)

INOVELLI_ALL_LED_EFFECT_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): INOVELLI_ALL_LED_EFFECT,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required("effect_type"): AllLEDEffectType.__getitem__,
        vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
        vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
    }
)

INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA = INOVELLI_ALL_LED_EFFECT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): INOVELLI_INDIVIDUAL_LED_EFFECT,
        vol.Required("effect_type"): SingleLEDEffectType.__getitem__,
        vol.Required("led_number"): vol.All(vol.Coerce(int), vol.Range(0, 6)),
    }
)

ACTION_SCHEMA_MAP = {
    INOVELLI_ALL_LED_EFFECT: INOVELLI_ALL_LED_EFFECT_SCHEMA,
    INOVELLI_INDIVIDUAL_LED_EFFECT: INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA,
}

ACTION_SCHEMA = vol.Any(
    INOVELLI_ALL_LED_EFFECT_SCHEMA,
    INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA,
    DEFAULT_ACTION_SCHEMA,
)

# Maps a (cluster_id) the device must expose to the available actions.
DEVICE_ACTIONS_BY_CLUSTER_ID: dict[int, list[dict[str, str]]] = {
    IasWd.cluster_id: [
        {CONF_TYPE: ACTION_SQUAWK, CONF_DOMAIN: DOMAIN},
        {CONF_TYPE: ACTION_WARN, CONF_DOMAIN: DOMAIN},
    ],
    INOVELLI_CLUSTER_ID: [
        {CONF_TYPE: INOVELLI_ALL_LED_EFFECT, CONF_DOMAIN: DOMAIN},
        {CONF_TYPE: INOVELLI_INDIVIDUAL_LED_EFFECT, CONF_DOMAIN: DOMAIN},
    ],
}

DEVICE_ACTION_TYPES = {
    ACTION_SQUAWK: ZHA_ACTION_TYPE_SERVICE_CALL,
    ACTION_WARN: ZHA_ACTION_TYPE_SERVICE_CALL,
    INOVELLI_ALL_LED_EFFECT: ZHA_ACTION_TYPE_CLUSTER_COMMAND,
    INOVELLI_INDIVIDUAL_LED_EFFECT: ZHA_ACTION_TYPE_CLUSTER_COMMAND,
}

DEVICE_ACTION_SCHEMAS = {
    INOVELLI_ALL_LED_EFFECT: vol.Schema(
        {
            vol.Required("effect_type"): vol.In(AllLEDEffectType.__members__.keys()),
            vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
            vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
        }
    ),
    INOVELLI_INDIVIDUAL_LED_EFFECT: vol.Schema(
        {
            vol.Required("led_number"): vol.All(vol.Coerce(int), vol.Range(0, 6)),
            vol.Required("effect_type"): vol.In(SingleLEDEffectType.__members__.keys()),
            vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
            vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
        }
    ),
}

SERVICE_NAMES = {
    ACTION_SQUAWK: SERVICE_WARNING_DEVICE_SQUAWK,
    ACTION_WARN: SERVICE_WARNING_DEVICE_WARN,
}

# Maps a cluster-command action type to the (cluster_id, command_name) that
# implements it.
CLUSTER_COMMAND_MAPPINGS: dict[str, tuple[int, str]] = {
    INOVELLI_ALL_LED_EFFECT: (INOVELLI_CLUSTER_ID, "led_effect"),
    INOVELLI_INDIVIDUAL_LED_EFFECT: (INOVELLI_CLUSTER_ID, "individual_led_effect"),
}

# Maps schema field name → ZCL command kwarg name.
INOVELLI_FIELD_TO_ZCL_KWARG = {
    "effect_type": "led_effect",
    "color": "led_color",
    "level": "led_level",
    "duration": "led_duration",
    "led_number": "led_number",
}


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Perform an action based on configuration."""
    await ZHA_ACTION_TYPES[DEVICE_ACTION_TYPES[config[CONF_TYPE]]](
        hass, config, variables, context
    )


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    schema = ACTION_SCHEMA_MAP.get(config[CONF_TYPE], DEFAULT_ACTION_SCHEMA)
    return schema(config)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions."""
    try:
        zha_device = async_get_zha_device_proxy(hass, device_id).device
    except KeyError, AttributeError:
        return []
    cluster_ids = {
        cluster_id
        for ep_id, endpoint in zha_device.device.endpoints.items()
        if ep_id != 0
        for cluster_id in endpoint.in_clusters
    }
    actions: list[dict[str, str]] = []
    for required_cluster_id, cluster_actions in DEVICE_ACTIONS_BY_CLUSTER_ID.items():
        if required_cluster_id in cluster_ids:
            actions.extend(cluster_actions)
    for action in actions:
        action[CONF_DEVICE_ID] = device_id
    return actions


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    if (fields := DEVICE_ACTION_SCHEMAS.get(config[CONF_TYPE])) is None:
        return {}
    return {"extra_fields": fields}


async def _execute_service_based_action(
    hass: HomeAssistant,
    config: dict[str, Any],
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    action_type = config[CONF_TYPE]
    service_name = SERVICE_NAMES[action_type]
    try:
        zha_device = async_get_zha_device_proxy(hass, config[CONF_DEVICE_ID]).device
    except KeyError, AttributeError:
        return

    service_data = {ATTR_IEEE: str(zha_device.ieee)}

    await hass.services.async_call(
        DOMAIN, service_name, service_data, blocking=True, context=context
    )


def _find_cluster(zha_device, cluster_id: int):
    """Return the first server cluster matching `cluster_id` on the device."""
    for ep_id, endpoint in zha_device.device.endpoints.items():
        if ep_id == 0:
            continue
        cluster = endpoint.in_clusters.get(cluster_id)
        if cluster is not None:
            return cluster
    return None


async def _execute_cluster_command_based_action(
    hass: HomeAssistant,
    config: dict[str, Any],
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    action_type = config[CONF_TYPE]
    cluster_id, command_name = CLUSTER_COMMAND_MAPPINGS[action_type]
    try:
        zha_device = async_get_zha_device_proxy(hass, config[CONF_DEVICE_ID]).device
    except KeyError, AttributeError:
        return

    cluster = _find_cluster(zha_device, cluster_id)
    if cluster is None or not hasattr(cluster, command_name):
        raise InvalidDeviceAutomationConfig(
            f"Unable to execute cluster command action: cluster 0x{cluster_id:04x}"
            f" command {command_name!r} not available"
        )

    kwargs = {
        zcl_kwarg: config[field]
        for field, zcl_kwarg in INOVELLI_FIELD_TO_ZCL_KWARG.items()
        if field in config
    }

    try:
        await getattr(cluster, command_name)(**kwargs)
    except ZHAException as err:
        raise HomeAssistantError(err) from err


ZHA_ACTION_TYPES = {
    ZHA_ACTION_TYPE_SERVICE_CALL: _execute_service_based_action,
    ZHA_ACTION_TYPE_CLUSTER_COMMAND: _execute_cluster_command_based_action,
}
