"""The Blue Current integration."""

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import BCU_APP, CHARGING_CARD_ID, DOMAIN, SERVICE_START_CHARGE_SESSION

SERVICE_START_CHARGE_SESSION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        # When no charging card is provided, use no charging card
        # (BCU_APP = no charging card).
        vol.Optional(CHARGING_CARD_ID, default=BCU_APP): cv.string,
    }
)


async def start_charge_session(service_call: ServiceCall) -> None:
    """Start a charge session with the provided device and charge card ID."""
    # When no charge card is provided, use the default charge card
    # set in the config flow.
    charging_card_id = service_call.data[CHARGING_CARD_ID]

    device, config_entry = service.async_get_device_and_config_entry(
        service_call.hass, DOMAIN, service_call.data[CONF_DEVICE_ID]
    )

    connector = config_entry.runtime_data

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
