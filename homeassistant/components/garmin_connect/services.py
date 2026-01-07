"""Services for Garmin Connect integration."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

if TYPE_CHECKING:
    from aiogarmin import GarminClient

    from .coordinator import GarminConnectCoordinators

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_SET_ACTIVE_GEAR = "set_active_gear"
SERVICE_ADD_BODY_COMPOSITION = "add_body_composition"
SERVICE_ADD_BLOOD_PRESSURE = "add_blood_pressure"
SERVICE_CREATE_ACTIVITY = "create_activity"
SERVICE_UPLOAD_ACTIVITY = "upload_activity"
SERVICE_ADD_GEAR_TO_ACTIVITY = "add_gear_to_activity"

# Service schemas
SET_ACTIVE_GEAR_SCHEMA = vol.Schema(
    {
        vol.Optional("gear_uuid"): cv.string,
        vol.Optional("entity_id"): cv.entity_id,
        vol.Required("activity_type"): vol.In(
            ["running", "cycling", "hiking", "walking", "swimming", "other"]
        ),
        vol.Optional("setting", default="set this as default, unset others"): vol.In(
            ["set this as default, unset others", "set as default", "unset default"]
        ),
    }
)

ADD_BODY_COMPOSITION_SCHEMA = vol.Schema(
    {
        vol.Required("weight"): vol.Coerce(float),
        vol.Optional("timestamp"): cv.string,
        vol.Optional("bmi"): vol.Coerce(float),
        vol.Optional("percent_fat"): vol.Coerce(float),
        vol.Optional("percent_hydration"): vol.Coerce(float),
        vol.Optional("visceral_fat_mass"): vol.Coerce(float),
        vol.Optional("bone_mass"): vol.Coerce(float),
        vol.Optional("muscle_mass"): vol.Coerce(float),
        vol.Optional("basal_met"): vol.Coerce(float),
        vol.Optional("active_met"): vol.Coerce(float),
        vol.Optional("physique_rating"): vol.Coerce(float),
        vol.Optional("metabolic_age"): vol.Coerce(float),
        vol.Optional("visceral_fat_rating"): vol.Coerce(float),
    }
)

ADD_BLOOD_PRESSURE_SCHEMA = vol.Schema(
    {
        vol.Required("systolic"): vol.All(vol.Coerce(int), vol.Range(min=60, max=250)),
        vol.Required("diastolic"): vol.All(vol.Coerce(int), vol.Range(min=40, max=150)),
        vol.Required("pulse"): vol.All(vol.Coerce(int), vol.Range(min=30, max=220)),
        vol.Optional("timestamp"): cv.string,
        vol.Optional("notes"): cv.string,
    }
)

CREATE_ACTIVITY_SCHEMA = vol.Schema(
    {
        vol.Required("activity_name"): cv.string,
        vol.Required("activity_type"): vol.In(
            [
                "running",
                "cycling",
                "walking",
                "hiking",
                "swimming",
                "fitness_equipment",
                "other",
            ]
        ),
        vol.Optional("start_datetime"): cv.string,
        vol.Required("duration_min"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1440)
        ),
        vol.Optional("distance_km", default=0.0): vol.Coerce(float),
        vol.Optional("time_zone"): cv.string,
    }
)

UPLOAD_ACTIVITY_SCHEMA = vol.Schema(
    {
        vol.Required("file_path"): cv.string,
    }
)

ADD_GEAR_TO_ACTIVITY_SCHEMA = vol.Schema(
    {
        vol.Required("activity_id"): vol.Coerce(int),
        vol.Optional("gear_uuid"): cv.string,
        vol.Optional("entity_id"): cv.entity_id,
    }
)


def _get_client(hass: HomeAssistant) -> GarminClient:
    """Get the Garmin client from the first available config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_integration_configured",
        )

    entry = entries[0]
    if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="integration_not_loaded",
        )

    # Get client from any coordinator (they all share the same client)
    coordinators: GarminConnectCoordinators = entry.runtime_data
    return coordinators.core.client


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Garmin Connect services."""

    async def handle_set_active_gear(call: ServiceCall) -> None:
        """Handle set_active_gear service call."""
        client = _get_client(hass)

        activity_type = call.data["activity_type"]
        setting = call.data["setting"]

        # Get gear_uuid - either directly or from entity
        gear_uuid = call.data.get("gear_uuid")

        if not gear_uuid:
            # Try to extract from entity
            entity_id = call.data.get("entity_id")
            if not entity_id:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="no_gear_specified",
                )

            state = hass.states.get(entity_id)
            if not state:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="entity_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )

            gear_uuid = state.attributes.get("gear_uuid")
            if not gear_uuid:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="gear_uuid_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )

        try:
            await client.set_active_gear(
                activity_type=activity_type,
                setting=setting,
                gear_uuid=gear_uuid,
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_active_gear_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_add_body_composition(call: ServiceCall) -> None:
        """Handle add_body_composition service call."""
        client = _get_client(hass)

        try:
            await client.add_body_composition(
                timestamp=call.data.get("timestamp"),
                weight=call.data["weight"],
                percent_fat=call.data.get("percent_fat"),
                percent_hydration=call.data.get("percent_hydration"),
                visceral_fat_mass=call.data.get("visceral_fat_mass"),
                bone_mass=call.data.get("bone_mass"),
                muscle_mass=call.data.get("muscle_mass"),
                basal_met=call.data.get("basal_met"),
                active_met=call.data.get("active_met"),
                physique_rating=call.data.get("physique_rating"),
                metabolic_age=call.data.get("metabolic_age"),
                visceral_fat_rating=call.data.get("visceral_fat_rating"),
                bmi=call.data.get("bmi"),
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_body_composition_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_add_blood_pressure(call: ServiceCall) -> None:
        """Handle add_blood_pressure service call."""
        client = _get_client(hass)

        try:
            await client.set_blood_pressure(
                systolic=call.data["systolic"],
                diastolic=call.data["diastolic"],
                pulse=call.data["pulse"],
                timestamp=call.data.get("timestamp"),
                notes=call.data.get("notes", ""),
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_blood_pressure_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_create_activity(call: ServiceCall) -> None:
        """Handle create_activity service call."""
        client = _get_client(hass)

        # Default to now if not provided
        start_datetime = call.data.get("start_datetime")
        if not start_datetime:
            start_datetime = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000")
        elif "." not in start_datetime:
            # API requires milliseconds format: "2023-12-02T10:00:00.000"
            start_datetime = f"{start_datetime}.000"
        # Default to HA's configured timezone
        time_zone = call.data.get("time_zone") or str(hass.config.time_zone)

        try:
            await client.create_activity(
                activity_name=call.data["activity_name"],
                activity_type=call.data["activity_type"],
                start_datetime=start_datetime,
                duration_min=call.data["duration_min"],
                distance_km=call.data.get("distance_km", 0.0),
                time_zone=time_zone,
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="create_activity_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_upload_activity(call: ServiceCall) -> None:
        """Handle upload_activity service call."""
        client = _get_client(hass)
        file_path = call.data["file_path"]

        # Resolve relative paths to config directory
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(hass.config.path(file_path))

        if not path.is_file():
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="file_not_found",
                translation_placeholders={"file_path": str(path)},
            )

        try:
            await client.upload_activity(str(path))
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="upload_activity_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def handle_add_gear_to_activity(call: ServiceCall) -> None:
        """Handle add_gear_to_activity service call."""
        client = _get_client(hass)

        activity_id = call.data["activity_id"]

        # Get gear_uuid - either directly or from entity
        gear_uuid = call.data.get("gear_uuid")

        if not gear_uuid:
            entity_id = call.data.get("entity_id")
            if not entity_id:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="no_gear_specified",
                )

            state = hass.states.get(entity_id)
            if not state:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="entity_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )

            gear_uuid = state.attributes.get("gear_uuid")
            if not gear_uuid:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="gear_uuid_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )

        try:
            await client.add_gear_to_activity(
                gear_uuid=gear_uuid,
                activity_id=activity_id,
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="add_gear_to_activity_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_GEAR,
        handle_set_active_gear,
        schema=SET_ACTIVE_GEAR_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BODY_COMPOSITION,
        handle_add_body_composition,
        schema=ADD_BODY_COMPOSITION_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BLOOD_PRESSURE,
        handle_add_blood_pressure,
        schema=ADD_BLOOD_PRESSURE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_ACTIVITY,
        handle_create_activity,
        schema=CREATE_ACTIVITY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_ACTIVITY,
        handle_upload_activity,
        schema=UPLOAD_ACTIVITY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_GEAR_TO_ACTIVITY,
        handle_add_gear_to_activity,
        schema=ADD_GEAR_TO_ACTIVITY_SCHEMA,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Garmin Connect services."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_ACTIVE_GEAR)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_BODY_COMPOSITION)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_BLOOD_PRESSURE)
    hass.services.async_remove(DOMAIN, SERVICE_CREATE_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_UPLOAD_ACTIVITY)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_GEAR_TO_ACTIVITY)
