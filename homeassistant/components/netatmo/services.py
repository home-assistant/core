"""Services for the Netatmo integration."""

import probatio

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.climate import ATTR_PRESET_MODE, DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_PERSONS
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.service import async_register_platform_entity_service

from .climate import THERM_MODES
from .const import (
    ATTR_CAMERA_LIGHT_MODE,
    ATTR_END_DATETIME,
    ATTR_PERSON,
    ATTR_SCHEDULE_NAME,
    ATTR_TARGET_TEMPERATURE,
    ATTR_TIME_PERIOD,
    CAMERA_LIGHT_MODES,
    DOMAIN,
    SERVICE_CLEAR_TEMPERATURE_SETTING,
    SERVICE_SET_CAMERA_LIGHT,
    SERVICE_SET_PERSON_AWAY,
    SERVICE_SET_PERSONS_HOME,
    SERVICE_SET_PRESET_MODE_WITH_END_DATETIME,
    SERVICE_SET_SCHEDULE,
    SERVICE_SET_TEMPERATURE_WITH_END_DATETIME,
    SERVICE_SET_TEMPERATURE_WITH_TIME_PERIOD,
)
from .coordinator import NetatmoConfigEntry, async_get_loaded_entry
from .webhook import async_register_webhook, async_unregister_webhook

SERVICE_REGISTER_WEBHOOK = "register_webhook"
SERVICE_UNREGISTER_WEBHOOK = "unregister_webhook"


def _get_loaded_entry(hass: HomeAssistant) -> NetatmoConfigEntry:
    """Return the loaded config entry or raise if unavailable."""
    if (entry := async_get_loaded_entry(hass)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    return entry


def _deprecate(hass: HomeAssistant, service: str) -> None:
    """Warn and raise a repair issue for the deprecated webhook actions."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_service_{service}",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_webhook_service",
    )


async def _register_webhook(call: ServiceCall) -> None:
    """Handle the deprecated register_webhook action."""
    _deprecate(call.hass, SERVICE_REGISTER_WEBHOOK)
    entry = _get_loaded_entry(call.hass)
    # Drop any existing registration first so re-registering an already-active
    # webhook does not raise "Handler is already defined!".
    await async_unregister_webhook(call.hass, entry)
    await async_register_webhook(call.hass, entry)


async def _unregister_webhook(call: ServiceCall) -> None:
    """Handle the deprecated unregister_webhook action."""
    _deprecate(call.hass, SERVICE_UNREGISTER_WEBHOOK)
    await async_unregister_webhook(call.hass, _get_loaded_entry(call.hass))


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Netatmo services."""
    hass.services.async_register(DOMAIN, SERVICE_REGISTER_WEBHOOK, _register_webhook)
    hass.services.async_register(
        DOMAIN, SERVICE_UNREGISTER_WEBHOOK, _unregister_webhook
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_PERSONS_HOME,
        entity_domain=CAMERA_DOMAIN,
        func="_service_set_persons_home",
        schema={
            probatio.Required(ATTR_PERSONS): probatio.All(
                probatio.EnsureList(), [cv.string]
            )
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_PERSON_AWAY,
        entity_domain=CAMERA_DOMAIN,
        func="_service_set_person_away",
        schema={probatio.Optional(ATTR_PERSON): cv.string},
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_CAMERA_LIGHT,
        entity_domain=CAMERA_DOMAIN,
        func="_service_set_camera_light",
        schema={
            probatio.Required(ATTR_CAMERA_LIGHT_MODE): probatio.In(CAMERA_LIGHT_MODES)
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SCHEDULE,
        entity_domain=CLIMATE_DOMAIN,
        func="_async_service_set_schedule",
        schema={probatio.Required(ATTR_SCHEDULE_NAME): cv.string},
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_PRESET_MODE_WITH_END_DATETIME,
        entity_domain=CLIMATE_DOMAIN,
        func="_async_service_set_preset_mode_with_end_datetime",
        schema={
            probatio.Required(ATTR_PRESET_MODE): probatio.In(THERM_MODES),
            probatio.Required(ATTR_END_DATETIME): cv.datetime,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TEMPERATURE_WITH_END_DATETIME,
        entity_domain=CLIMATE_DOMAIN,
        func="_async_service_set_temperature_with_end_datetime",
        schema={
            probatio.Required(ATTR_TARGET_TEMPERATURE): probatio.All(
                probatio.Coerce(float), probatio.Range(min=7, max=30)
            ),
            probatio.Required(ATTR_END_DATETIME): cv.datetime,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TEMPERATURE_WITH_TIME_PERIOD,
        entity_domain=CLIMATE_DOMAIN,
        func="_async_service_set_temperature_with_time_period",
        schema={
            probatio.Required(ATTR_TARGET_TEMPERATURE): probatio.All(
                probatio.Coerce(float), probatio.Range(min=7, max=30)
            ),
            probatio.Required(ATTR_TIME_PERIOD): probatio.All(
                cv.time_period,
                cv.positive_timedelta,
            ),
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_TEMPERATURE_SETTING,
        entity_domain=CLIMATE_DOMAIN,
        func="_async_service_clear_temperature_setting",
        schema=None,
    )
