"""Provides device actions for ZHA devices."""

from typing import Any

import voluptuous as vol
from zhaquirks.inovelli.types import AllLEDEffectType, SingleLEDEffectType
from zigpy.zcl.clusters.security import IasWd

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN
from .helpers import async_get_zha_device_proxy, convert_zha_error_to_ha_error
from .websocket_api import SERVICE_WARNING_DEVICE_SQUAWK, SERVICE_WARNING_DEVICE_WARN

# mypy: disallow-any-generics

INOVELLI_CLUSTER_ID = 0xFC31

ACTION_SQUAWK = "squawk"
ACTION_WARN = "warn"
ATTR_IEEE = "ieee"
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

# Maps a cluster_id the device must expose to the available actions.
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


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Perform an action based on configuration."""
    action_type = config[CONF_TYPE]
    handler = ACTION_HANDLERS[action_type]
    await handler(hass, config, context)


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
            actions.extend(
                {**action, CONF_DEVICE_ID: device_id} for action in cluster_actions
            )
    return actions


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    if (fields := DEVICE_ACTION_SCHEMAS.get(config[CONF_TYPE])) is None:
        return {}
    return {"extra_fields": fields}


async def _execute_siren_service(
    hass: HomeAssistant,
    config: dict[str, Any],
    context: Context | None,
) -> None:
    try:
        zha_device = async_get_zha_device_proxy(hass, config[CONF_DEVICE_ID]).device
    except KeyError, AttributeError:
        return
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NAMES[config[CONF_TYPE]],
        {ATTR_IEEE: str(zha_device.ieee)},
        blocking=True,
        context=context,
    )


def _find_inovelli_cluster(hass: HomeAssistant, config: dict[str, Any]) -> Any:
    try:
        zha_device = async_get_zha_device_proxy(hass, config[CONF_DEVICE_ID]).device
    except (KeyError, AttributeError) as err:
        raise InvalidDeviceAutomationConfig(
            f"ZHA device {config[CONF_DEVICE_ID]} not found"
        ) from err
    try:
        return zha_device.device.find_cluster(cluster_id=INOVELLI_CLUSTER_ID)
    except ValueError as err:
        raise InvalidDeviceAutomationConfig(
            f"Device does not expose Inovelli cluster 0x{INOVELLI_CLUSTER_ID:04x}"
        ) from err


async def _execute_inovelli_all_led_effect(
    hass: HomeAssistant,
    config: dict[str, Any],
    context: Context | None,
) -> None:
    cluster = _find_inovelli_cluster(hass, config)

    async with convert_zha_error_to_ha_error():
        await cluster.led_effect(
            led_effect=config["effect_type"],
            led_color=config["color"],
            led_level=config["level"],
            led_duration=config["duration"],
        )


async def _execute_inovelli_individual_led_effect(
    hass: HomeAssistant,
    config: dict[str, Any],
    context: Context | None,
) -> None:
    cluster = _find_inovelli_cluster(hass, config)

    async with convert_zha_error_to_ha_error():
        await cluster.individual_led_effect(
            led_effect=config["effect_type"],
            led_color=config["color"],
            led_level=config["level"],
            led_duration=config["duration"],
            led_number=config["led_number"],
        )


ACTION_HANDLERS = {
    ACTION_SQUAWK: _execute_siren_service,
    ACTION_WARN: _execute_siren_service,
    INOVELLI_ALL_LED_EFFECT: _execute_inovelli_all_led_effect,
    INOVELLI_INDIVIDUAL_LED_EFFECT: _execute_inovelli_individual_led_effect,
}
