"""Services for the La Marzocco integration."""

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from lmcloud.exceptions import AuthFail, RequestNotSuccessful
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_CONFIG_ENTRY,
    CONF_DAY_OF_WEEK,
    CONF_ENABLE,
    CONF_HOUR_OFF,
    CONF_HOUR_ON,
    CONF_MINUTE_OFF,
    CONF_MINUTE_ON,
    DAYS,
    DOMAIN,
    SERVICE_AUTO_ON_OFF_ENABLE,
    SERVICE_AUTO_ON_OFF_TIMES,
)
from .coordinator import LaMarzoccoUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        )
    }
)


SET_AUTO_ON_OFF_ENABLE_SCHEMA = CONFIG_ENTRY_SCHEMA.extend(
    {
        vol.Required(CONF_DAY_OF_WEEK): vol.In(DAYS),
        vol.Required(CONF_ENABLE): cv.boolean,
    }
)

SET_AUTO_ON_OFF_TIMES_SCHEMA = CONFIG_ENTRY_SCHEMA.extend(
    {
        vol.Required(CONF_DAY_OF_WEEK): vol.In(DAYS),
        vol.Required(CONF_HOUR_ON): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Optional(CONF_MINUTE_ON, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=59)
        ),
        vol.Required(CONF_HOUR_OFF): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Optional(CONF_MINUTE_OFF, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=59)
        ),
    }
)


async def __call_service(
    func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any
) -> None:
    """Call a service and handle exceptions."""
    try:
        await func(*args, **kwargs)
    except (AuthFail, RequestNotSuccessful, TimeoutError) as ex:
        raise HomeAssistantError("Service call encountered error: %s" % str(ex)) from ex


def __get_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> LaMarzoccoUpdateCoordinator:
    """Get the coordinator from the entry."""
    entry_id: str = call.data[CONF_CONFIG_ENTRY]
    entry: ConfigEntry | None = hass.config_entries.async_get_entry(entry_id)

    if not entry:
        raise ServiceValidationError(
            f"Invalid config entry: {entry_id}",
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
            translation_placeholders={
                "config_entry": entry_id,
            },
        )
    if entry.state != ConfigEntryState.LOADED:
        raise ServiceValidationError(
            f"Config entry {entry.title} is not loaded",
            translation_domain=DOMAIN,
            translation_key="unloaded_config_entry",
            translation_placeholders={
                "config_entry": entry.title,
            },
        )
    coordinator: LaMarzoccoUpdateCoordinator = hass.data[DOMAIN][entry_id]
    return coordinator


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Create and register services for the La Marzocco integration."""

    async def _set_auto_on_off_enable(service: ServiceCall) -> None:
        """Service call to enable auto on/off."""

        day_of_week = service.data[CONF_DAY_OF_WEEK]
        enable = service.data[CONF_ENABLE]

        coordinator = __get_coordinator(hass, service)

        _LOGGER.debug("Setting auto on/off for %s to %s", day_of_week, enable)
        await __call_service(
            coordinator.lm.set_auto_on_off_enable,
            day_of_week=day_of_week,
            enable=enable,
        )

    async def _set_auto_on_off_times(service: ServiceCall) -> None:
        """Service call to configure auto on/off hours for a day."""
        day_of_week = service.data[CONF_DAY_OF_WEEK]
        hour_on = service.data[CONF_HOUR_ON]
        minute_on = service.data[CONF_MINUTE_ON]
        hour_off = service.data[CONF_HOUR_OFF]
        minute_off = service.data[CONF_MINUTE_OFF]

        coordinator = __get_coordinator(hass, service)

        _LOGGER.debug(
            "Setting auto on/off hours for %s from %s:%s to %s:%s",
            day_of_week,
            hour_on,
            minute_on,
            hour_off,
            minute_off,
        )
        await __call_service(
            coordinator.lm.set_auto_on_off,
            day_of_week=day_of_week,
            hour_on=hour_on,
            minute_on=minute_on,
            hour_off=hour_off,
            minute_off=minute_off,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_ENABLE,
        _set_auto_on_off_enable,
        schema=SET_AUTO_ON_OFF_ENABLE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_AUTO_ON_OFF_TIMES,
        _set_auto_on_off_times,
        schema=SET_AUTO_ON_OFF_TIMES_SCHEMA,
    )
