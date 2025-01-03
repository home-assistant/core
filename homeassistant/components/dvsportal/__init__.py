"""Home Assistant DVS Portal Integration.

This integration allows Home Assistant to interact with the DVS Portal API,
retrieving data such as parking balance, and managing car reservations.
"""

import asyncio
from datetime import datetime
import logging
from typing import TypedDict

from dvsportal import DVSPortal, exceptions as dvs_exceptions
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import DVSPortalCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_CREATE_RESERVATION = "create_reservation"

CREATE_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_id,
        vol.Optional("entry_id"): cv.string,
        vol.Optional("license_plate_value"): cv.string,
        vol.Optional("license_plate_name"): cv.string,
        vol.Optional("date_from"): cv.datetime,
        vol.Optional("date_until"): cv.datetime,
    }
)

SERVICE_END_RESERVATION = "end_reservation"

END_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)


class DVSPortalRuntimeData(TypedDict):
    """Typed runtime data for dvsportal."""

    dvs_portal: DVSPortal
    coordinator: DVSPortalCoordinator
    ha_registered_license_plates: set[str]


type DVSPortalConfigEntry = config_entries.ConfigEntry[DVSPortalRuntimeData]


async def async_setup(hass: core.HomeAssistant, config: ConfigType) -> bool:
    """Set up the dvsportal integration."""

    async def create_reservation_service(call: core.ServiceCall):
        """Handle creating a reservation."""
        entry_id: str | None = call.data.get("entry_id")
        if not entry_id or not (entry := hass.config_entries.async_get_entry(entry_id)):
            raise exceptions.ServiceValidationError(f"Entry {entry_id} not found")
        if entry.state != config_entries.ConfigEntryState.LOADED:
            raise exceptions.ServiceValidationError(f"Entry {entry_id} not loaded")

        runtime_data: DVSPortalRuntimeData = entry.runtime_data
        dvs_portal = runtime_data["dvs_portal"]
        coordinator = runtime_data["coordinator"]

        entry_id = call.data.get("entry_id")
        entity_id = call.data.get("entity_id")
        license_plate_value = call.data.get("license_plate_value")
        license_plate_name = call.data.get("license_plate_name")
        date_from = call.data.get("date_from")
        date_until = call.data.get("date_until")

        if entity_id:
            entity = hass.states.get(entity_id)
            if entity is None:
                _LOGGER.error("Entity not found")
                raise HomeAssistantError(f"Entity {entity_id} not found")
            license_plate_value = entity.attributes.get("license_plate")

        if not license_plate_value:
            _LOGGER.error(
                "'license_plate_value' is required if 'entity_id' is not provided"
            )
            raise HomeAssistantError(
                "'license_plate_value' is required if 'entity_id' is not provided"
            )

        try:
            if date_from and not isinstance(date_from, datetime):
                date_from = datetime.fromisoformat(date_from)
            if date_until and not isinstance(date_until, datetime):
                date_until = datetime.fromisoformat(date_until)
        except (ValueError, TypeError) as ex:
            _LOGGER.exception("Invalid date format")
            raise HomeAssistantError(
                "Invalid date format for date_from or date_until"
            ) from ex

        if date_from and date_until and date_from >= date_until:
            raise HomeAssistantError("'date_until' must be later than 'date_from'")

        try:
            tasks = [
                dvs_portal.create_reservation(
                    license_plate_value=license_plate_value,
                    license_plate_name=license_plate_name,
                    date_from=date_from,
                    date_until=date_until,
                )
            ]
            if license_plate_name:
                tasks.append(
                    dvs_portal.store_license_plate(
                        license_plate=license_plate_value,
                        name=license_plate_name,
                    )
                )
            await asyncio.gather(*tasks)
        except Exception as e:
            _LOGGER.exception("Failed to create reservation")
            raise HomeAssistantError("Failed to create reservation") from e
        finally:
            await coordinator.async_request_refresh()

    async def end_reservation_service(call: core.ServiceCall):
        """Handle ending a reservation."""
        entry_id = call.data.get("entry_id")
        if not entry_id or not (entry := hass.config_entries.async_get_entry(entry_id)):
            raise exceptions.ServiceValidationError(f"Entry {entry_id} not found")
        if entry.state != config_entries.ConfigEntryState.LOADED:
            raise exceptions.ServiceValidationError(f"Entry {entry_id} not loaded")

        runtime_data: DVSPortalRuntimeData = entry.runtime_data
        dvs_portal = runtime_data["dvs_portal"]
        coordinator = runtime_data["coordinator"]

        entity_id = call.data.get("entity_id", "")
        entity = hass.states.get(entity_id)
        if entity is None:
            raise HomeAssistantError(f"Entity {entity_id} not found")

        reservation_id = entity.attributes.get("reservation_id")
        if not reservation_id:
            raise HomeAssistantError(f"No reservation_id found for entity {entity_id}")

        try:
            await dvs_portal.end_reservation(reservation_id=reservation_id)
        except Exception as e:
            _LOGGER.exception("Failed to end reservation")
            raise HomeAssistantError("Failed to end reservation") from e
        finally:
            await coordinator.async_request_refresh()

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_RESERVATION,
        create_reservation_service,
        schema=CREATE_RESERVATION_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_END_RESERVATION,
        end_reservation_service,
        schema=END_RESERVATION_SCHEMA,
    )

    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: DVSPortalConfigEntry
) -> bool:
    """Set up the dvsportal component from a config entry."""

    api_host = entry.data[CONF_HOST]
    identifier = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    user_agent = entry.data.get("user_agent", "HomeAssistant")

    dvs_portal = DVSPortal(
        api_host=api_host,
        identifier=identifier,
        password=password,
        user_agent=user_agent,
    )

    try:
        await dvs_portal.token()
    except dvs_exceptions.DVSPortalConnectionError as ex:
        _LOGGER.exception("Error while connecting to server")
        raise exceptions.ConfigEntryNotReady("Device is offline") from ex
    except dvs_exceptions.DVSPortalAuthError as ex:
        _LOGGER.error("Authentication failed for DVSPortal")
        raise exceptions.ConfigEntryAuthFailed("Invalid authentication") from ex
    except dvs_exceptions.DVSPortalError as ex:
        _LOGGER.exception("Unknown error occurred while setting up DVSPortal")
        raise exceptions.ConfigEntryError("Unknown error occurred") from ex

    coordinator = DVSPortalCoordinator(hass, dvs_portal)

    await coordinator.async_refresh()

    entry.runtime_data = DVSPortalRuntimeData(
        dvs_portal=dvs_portal,
        coordinator=coordinator,
        ha_registered_license_plates=set(),
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    async def async_unload_entry(
        hass: core.HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Unload a config entry."""
        unload_ok = await hass.config_entries.async_forward_entry_unload(
            entry, "sensor"
        )
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)

        return unload_ok

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{entry.entry_id}_unload", async_unload_entry
        )
    )

    async def async_update_options(
        hass: core.HomeAssistant, entry: config_entries.ConfigEntry
    ):
        """Update options."""
        await hass.config_entries.async_reload(entry.entry_id)

    entry.add_update_listener(async_update_options)

    return True
