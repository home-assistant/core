"""EffortlessHome integration."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import voluptuous as vol
from oasira import OasiraAPIClient, OasiraAPIError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)

from .const import (
    DOMAIN,
    LABELS,
    NAME,
)
from .deviceclassgroupsync import async_setup_devicegroup


_LOGGER = logging.getLogger(__name__)


class HASSComponent:
    """Hasscomponent."""

    # Class-level property to hold the hass instance
    hass_instance = None

    @classmethod
    def set_hass(cls, hass: HomeAssistant) -> None:
        """Set Hass."""
        cls.hass_instance = hass

    @classmethod
    def get_hass(cls):
        """Get Hass."""
        return cls.hass_instance



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entry_id"] = entry.entry_id

    system_id = entry.data["system_id"]
    customer_id = entry.data["customer_id"]
    id_token = entry.data.get("id_token")

    if not system_id:
        raise HomeAssistantError("System ID is missing in configuration.")

    if not customer_id:
        raise HomeAssistantError("Customer ID is missing in configuration.")

    HASSComponent.set_hass(hass)

    # Initialize API client and fetch customer/system data
    async with OasiraAPIClient(
        system_id=system_id,
        id_token=id_token,
    ) as api_client:
        try:
            parsed_data = await api_client.get_customer_and_system()

            # Fetch plan features for this system
            plan_features = None
            try:
                plan_features = await api_client.get_plan_features_by_system_id()
            except Exception as pf_exc:
                _LOGGER.warning("Failed to fetch plan features: %s", pf_exc)
                plan_features = None

            hass.data[DOMAIN] = {
                "entry_id": entry.entry_id,
                "config_entry": entry,
                "fullname": parsed_data["fullname"],
                "phonenumber": parsed_data["phonenumber"],
                "emailaddress": parsed_data["emailaddress"],
                "ha_token": parsed_data["ha_token"],
                "ha_url": parsed_data["ha_url"],
                "ai_key": parsed_data["ai_key"],
                "ai_model": parsed_data["ai_model"],
                "email": parsed_data["emailaddress"],
                "username": parsed_data["emailaddress"],
                "systemid": system_id,
                "customerid": customer_id,
                "id_token": id_token,
                "refresh_token": entry.data.get("refresh_token"),
                "influx_url": parsed_data["influx_url"],
                "influx_token": parsed_data["influx_token"],
                "influx_bucket": parsed_data["influx_bucket"],
                "influx_org": parsed_data["influx_org"],
                "DaysHistoryToKeep": parsed_data["DaysHistoryToKeep"],
                "LowTemperatureWarning": parsed_data["LowTemperatureWarning"],
                "HighTemperatureWarning": parsed_data["HighTemperatureWarning"],
                "LowHumidityWarning": parsed_data["LowHumidityWarning"],
                "HighHumidityWarning": parsed_data["HighHumidityWarning"],
                "address_json": parsed_data["address_json"],
                "systemphotolurl": parsed_data["systemphotolurl"],
                "testmode": parsed_data["testmode"],
                "additional_contacts_json": parsed_data["additional_contacts_json"],
                "instructions_json": parsed_data["instructions_json"],
                "plan": parsed_data["name"],
                "plan_features": plan_features,
            }
        except OasiraAPIError as e:
            _LOGGER.error("Failed to fetch customer/system data: %s", e)
            if "401" in str(e):
                _LOGGER.info("Token expired, requesting reauth")
                entry.async_start_reauth(hass)
                return False
            raise HomeAssistantError(
                f"Failed to fetch customer/system data: {e}"
            ) from e

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, NAME)},
        name=NAME,
        manufacturer=NAME,
        model=NAME,
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["switch"])

    register_services(hass)

    # Labels are kept in sync during setup.
    label_registry = lr.async_get(hass)

    for desired in LABELS:
        try:
            label_registry.async_create(desired)
            _LOGGER.info("Created missing label: %s", desired)
        except ValueError:
            # Label already exists → ignore
            _LOGGER.info("Label already exists: %s", desired)

    async def after_home_assistant_started(event):
        """Call this function after Home Assistant has started."""
        await loaddevicegroups(None)

    # Listen for the 'homeassistant_started' event
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED, after_home_assistant_started
    )

    return True


def _deploy_latest_config_sync(hass: HomeAssistant):
    """Synchronous helper for deploying config."""
    integration_dir = os.path.dirname(os.path.abspath(__file__))

    source_themes_dir = os.path.join(integration_dir, "themes")
    source_blueprints_dir = os.path.join(integration_dir, "blueprints")
    source_dir = os.path.join(integration_dir, "www/effortlesshome")

    target_themes_dir = hass.config.path("themes")
    target_dir = hass.config.path("www/effortlesshome")
    target_blueprints_dir = hass.config.path("blueprints")

    # Ensure destination directories exist
    os.makedirs(target_themes_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(target_blueprints_dir, exist_ok=True)

    # Copy entire themes directory including subfolders and files
    if os.path.exists(source_themes_dir):
        shutil.copytree(source_themes_dir, target_themes_dir, dirs_exist_ok=True)

    if os.path.exists(source_blueprints_dir):
        shutil.copytree(
            source_blueprints_dir, target_blueprints_dir, dirs_exist_ok=True
        )

    if os.path.exists(source_dir):
        shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)


async def deploy_latest_config(hass: HomeAssistant):
    """Deploy latest: theme, cards, blueprints, etc."""
    _LOGGER.info("[EffortlessHome] Deploying latest configuration files...")
    await hass.async_add_executor_job(_deploy_latest_config_sync, hass)
    _LOGGER.info("[EffortlessHome] Configuration deployment complete.")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    await hass.config_entries.async_unload_platforms(entry, ["switch"])

    # Unregister the notify service
    hass.services.async_remove("effortlesshome", "clean_motion_files")
    hass.services.async_remove("effortlesshome", "create_event")
    hass.services.async_remove("effortlesshome", "update_entity")
    hass.services.async_remove("effortlesshome", "create_alert")
    hass.services.async_remove("effortlesshome", "deploy_latest_config")
    hass.services.async_remove("effortlesshome", "add_label_to_entity")

    return True


async def add_label_to_entity(call: ServiceCall) -> None:
    """Add a label to an entity."""
    entity_id = call.data.get("entity_id")
    label = call.data.get("label")

    if not entity_id or not label:
        _LOGGER.error(
            "entity_id and label are required for add_label_to_entity service"
        )
        return

    hass = HASSComponent.get_hass()
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if not entity_entry:
        _LOGGER.error(f"Entity not found: {entity_id}")
        return

    new_labels = set(entity_entry.labels)
    new_labels.add(label)

    ent_reg.async_update_entity(entity_id, labels=new_labels)
    _LOGGER.info(f"Added label '{label}' to entity '{entity_id}'")


@callback
def register_services(hass: HomeAssistant) -> None:
    """Register effortlesshome services."""

    hass.services.async_register(DOMAIN, "clean_motion_files", clean_motion_files)

    # Register our service with Home Assistant.
    hass.services.async_register(DOMAIN, "create_event", create_event)

    hass.services.async_register(DOMAIN, "update_entity", update_entity)

    hass.services.async_register(DOMAIN, "create_alert", create_alert)

    hass.services.async_register(
        DOMAIN, "deploy_latest_config", handle_deploy_latest_config
    )

    hass.services.async_register(
        DOMAIN,
        "add_label_to_entity",
        add_label_to_entity,
        schema=vol.Schema(
            {vol.Required("entity_id"): cv.entity_id, vol.Required("label"): cv.string}
        ),
    )


async def update_entity(call):
    """Handle the service call."""
    entity_id = call.data.get("entity_id")
    new_area = call.data.get("area_id")

    hass = HASSComponent.get_hass()
    ent_reg = er.async_get(hass)

    ent_reg.async_update_entity(entity_id, area_id=new_area)


async def loaddevicegroups(calldata) -> None:
    """Load device groups."""
    hass = HASSComponent.get_hass()
    await async_setup_devicegroup(hass)


async def create_event(call: ServiceCall) -> None:
    """Create event."""
    _LOGGER.info("create event calldata =%s", call.data)

    hass = HASSComponent.get_hass()

    entity_id = call.data.get("entity_id")
    if not entity_id:
        _LOGGER.error("entity_id is required for create_event service")
        return

    devicestate = hass.states.get(entity_id)
    sensor_device_class = None
    sensor_device_name = None

    if devicestate and devicestate.attributes.get("friendly_name"):
        sensor_device_name = devicestate.attributes["friendly_name"]

    if devicestate and devicestate.attributes.get("device_class"):
        sensor_device_class = devicestate.attributes["device_class"]

    if sensor_device_class is not None and sensor_device_name is not None:
        alarmstate = hass.data[DOMAIN].get("alarm_id")

        if alarmstate and alarmstate != "":
            alarmstatus = hass.data[DOMAIN].get("alarmstatus")

            if alarmstatus == "ACTIVE":
                alarmid = alarmstate
                _LOGGER.info("alarm id =%s", alarmid)

                # Call the API to create event
                systemid = hass.data[DOMAIN].get("systemid")
                id_token = hass.data[DOMAIN].get("id_token")

                event_data = {
                    "sensor_device_class": sensor_device_class,
                    "sensor_device_name": sensor_device_name,
                }

                _LOGGER.info("Calling create event API with payload: %s", event_data)

                async with OasiraAPIClient(
                    system_id=systemid,
                    id_token=id_token,
                ) as api_client:
                    try:
                        result = await api_client.create_event(alarmid, event_data)
                        _LOGGER.info("API response content: %s", result)
                        return result
                    except OasiraAPIError as e:
                        _LOGGER.error("Failed to create event: %s", e)
                        return None
            return None
        return None
    return None


async def create_alert(call: ServiceCall) -> None:
    """Create alert."""
    _LOGGER.info("create alert calldata =%s", call.data)

    hass = HASSComponent.get_hass()
    alert_type = call.data.get("alert_type")
    alert_description = call.data.get("alert_description")
    status = call.data.get("status")

    if not alert_type or not alert_description or not status:
        _LOGGER.error(
            "alert_type, alert_description, and status are required for create_alert service"
        )
        return

    alert_data = {
        "alert_type": alert_type,
        "alert_description": alert_description,
        "status": status,
    }

    # Call the API to create alert
    systemid = hass.data[DOMAIN].get("systemid")
    id_token = hass.data[DOMAIN].get("id_token")

    _LOGGER.info("Calling alert API with payload: %s", alert_data)

    async with OasiraAPIClient(
        system_id=systemid,
        id_token=id_token,
    ) as api_client:
        try:
            result = await api_client.create_alert(alert_data)
            _LOGGER.info("API response content: %s", result)
            return result
        except OasiraAPIError as e:
            _LOGGER.error("Failed to create alert: %s", e)
            return None


async def clean_motion_files(call: ServiceCall) -> None:
    """Execute the shell command to delete old snapshots."""
    age = call.data.get("age", 30)

    if not isinstance(age, int) or age < 1:
        _LOGGER.warning("Invalid age value %s, using default 30 days", age)
        age = 30

    command = f"find /media/snapshots/* -mtime +{age} -exec rm {{}} \\;"

    # Use subprocess to execute the shell command
    try:
        process = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if process.returncode == 0:
            _LOGGER.info("Successfully deleted old snapshots older than %s days", age)
        else:
            _LOGGER.error("Error deleting snapshots: %s", process.stderr.decode())
    except Exception as e:
        _LOGGER.error("Failed to clean motion files: %s", e)


async def handle_deploy_latest_config(call: ServiceCall) -> None:
    """Handle the service call."""
    hass = HASSComponent.get_hass()

    await deploy_latest_config(hass)

