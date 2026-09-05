"""Services for Nintendo Parental integration."""

from enum import StrEnum
import logging

from pynintendoparental.device import Device
from pynintendoparental.enum import SafeLaunchSetting
from pynintendoparental.player import Player
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_PIN
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    service,
)
from homeassistant.util.json import JsonValueType

from .const import ATTR_BONUS_TIME, DOMAIN
from .coordinator import NintendoParentalControlsConfigEntry
from .sensor import NintendoParentalControlsSensor

_LOGGER = logging.getLogger(__name__)


class NintendoParentalServices(StrEnum):
    """Store keys for Nintendo Parental services."""

    ADD_BONUS_TIME = "add_bonus_time"
    UPDATE_PIN_CODE = "update_pin_code"
    PLAYER_USAGE_REPORT = "player_usage_report"
    DEVICE_USAGE_REPORT = "device_usage_report"


@callback
def async_setup_services(
    hass: HomeAssistant,
):
    """Set up the Nintendo Parental services."""
    hass.services.async_register(
        domain=DOMAIN,
        service=NintendoParentalServices.ADD_BONUS_TIME,
        service_func=async_add_bonus_time,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_BONUS_TIME): vol.All(int, vol.Range(min=5, max=30)),
            }
        ),
    )
    hass.services.async_register(
        domain=DOMAIN,
        service=NintendoParentalServices.PLAYER_USAGE_REPORT,
        service_func=async_get_player_usage,
        supports_response=SupportsResponse.ONLY,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_ENTITY_ID): cv.string,
            }
        ),
    )
    hass.services.async_register(
        domain=DOMAIN,
        service=NintendoParentalServices.DEVICE_USAGE_REPORT,
        service_func=async_get_device_usage_report,
        supports_response=SupportsResponse.ONLY,
        schema=vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
            }
        ),
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        NintendoParentalServices.UPDATE_PIN_CODE,
        async_update_pin_code,
        vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(CONF_PIN): cv.string,
            }
        ),
    )


def _get_nintendo_device(hass: HomeAssistant, device_id: str) -> Device:
    """Get the Nintendo device from a device ID."""
    config_entry: NintendoParentalControlsConfigEntry
    device, config_entry = service.async_get_device_and_config_entry(
        hass, DOMAIN, device_id
    )
    nintendo_device_id = None
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            nintendo_device_id = identifier[1].split("_")[-1]
            break
    if (
        nintendo_device_id
        and nintendo_device_id in config_entry.runtime_data.api.devices
    ):
        return config_entry.runtime_data.api.devices[nintendo_device_id]
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_device",
    )


def _get_nintendo_player(hass: HomeAssistant, device: Device, entity_id: str) -> Player:
    """Return a given player for a given device."""
    prefix = f"{device.device_id}_"
    suffix = f"_{NintendoParentalControlsSensor.PLAYER_PLAYING_TIME}"
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None or entry.platform != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_entity"
        )
    if entry.unique_id.startswith(prefix) and entry.unique_id.endswith(suffix):
        player_id = entry.unique_id[len(prefix) : -len(suffix)]
        if player_id in device.players:
            return device.players.get_player(player_id)
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="invalid_player"
    )


def _build_player_app_report(player: Player) -> list[dict[str, JsonValueType]]:
    """Produce a player application report."""
    return [
        {
            "playing_time": app.playing_time,
            "name": app.application.name,
            "image": app.application.image_url,
            "whitelisted": app.application.safe_launch_setting
            == SafeLaunchSetting.ALLOW,
        }
        for app in player.apps
    ]


async def async_add_bonus_time(call: ServiceCall) -> None:
    """Add bonus time to a device."""
    data = call.data
    device_id: str = data[ATTR_DEVICE_ID]
    bonus_time: int = data[ATTR_BONUS_TIME]
    device = _get_nintendo_device(call.hass, device_id)
    return await device.add_extra_time(bonus_time)


async def async_update_pin_code(call: ServiceCall) -> None:
    """Update the PIN code for a device."""
    data = call.data
    device_id: str = data[ATTR_DEVICE_ID]
    new_pin: str = data[CONF_PIN]
    if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 8:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_pin_length",
        )
    device = _get_nintendo_device(call.hass, device_id)
    return await device.set_new_pin(new_pin)


async def async_get_player_usage(call: ServiceCall) -> dict:
    """Get player usage."""
    data = call.data
    device_id: str = data[ATTR_DEVICE_ID]
    entity_id: str = data[ATTR_ENTITY_ID]
    device = _get_nintendo_device(call.hass, device_id)
    player = _get_nintendo_player(call.hass, device, entity_id)
    return {"apps": _build_player_app_report(player)}


async def async_get_device_usage_report(call: ServiceCall) -> dict:
    """Return the device usage report."""
    data = call.data
    device_id: str = data[ATTR_DEVICE_ID]
    device = _get_nintendo_device(call.hass, device_id)
    return {
        player.nickname: _build_player_app_report(player) for player in device.players
    }
