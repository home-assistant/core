"""The Blue Current integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import BCU_APP, CHARGING_CARD_ID, DOMAIN, SERVICE_START_CHARGE_SESSION

SERVICE_START_CHARGE_SESSION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        # When no charging card is provided, use no charging card (BCU_APP = no charging card).
        vol.Optional(CHARGING_CARD_ID, default=BCU_APP): cv.string,
    }
)


async def start_charge_session(service_call: ServiceCall) -> None:
    """Start a charge session with the provided device and charge card ID."""
    # When no charge card is provided, use the default charge card set in the config flow.
    charging_card_id = service_call.data[CHARGING_CARD_ID]
    device_id = service_call.data[CONF_DEVICE_ID]

    # Get the device based on the given device ID.
    device = dr.async_get(service_call.hass).devices.get(device_id)

    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_device_id"
        )

    blue_current_config_entry: ConfigEntry | None = None

    for config_entry_id in device.config_entries:
        config_entry = service_call.hass.config_entries.async_get_entry(config_entry_id)
        if not config_entry or config_entry.domain != DOMAIN:
            # Not the blue_current config entry.
            continue

        if config_entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="config_entry_not_loaded"
            )

        blue_current_config_entry = config_entry
        break

    if not blue_current_config_entry:
        # The device is not connected to a valid blue_current config entry.
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_config_entry"
        )

    connector = blue_current_config_entry.runtime_data

    # Get the evse_id from the identifier of the device.
    evse_id = next(
        identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN
    )

    await connector.client.start_session(evse_id, charging_card_id)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CHARGE_SESSION,
        start_charge_session,
        SERVICE_START_CHARGE_SESSION_SCHEMA,
    )
