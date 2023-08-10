"""The FlexMeasures integration."""
from __future__ import annotations

from datetime import datetime
import logging

import pytz

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import state as state_helper
from homeassistant.helpers.typing import ConfigType

from .api import S2FlexMeasuresClient, async_register_s2_api
from .const import DOMAIN

ATTR_NAME = "name"
DEFAULT_NAME = "World"


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up is called when Home Assistant is loading our component."""

    # Return boolean to indicate that initialization was successful.
    return True


# For your initial PR, limit it to 1 platform.
# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FlexMeasures from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    config_data = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    config_data["unsub_options_update_listener"] = unsub_options_update_listener
    client = S2FlexMeasuresClient(
        host=config_data["host"],
        email=config_data["username"],
        password=config_data["password"],
    )
    config_data["coordinator"] = client
    hass.data[DOMAIN][entry.entry_id] = config_data

    async def handle_api(call):
        """Handle the service call to the FlexMeasures REST API."""
        call.data.get(ATTR_NAME, DEFAULT_NAME)
        method = call.data.get("method")
        call_dict = {**call.data}
        call_dict.pop("method")
        if method == "post_measurements":
            logging.info("post measurement")
            await getattr(client, method)(**call_dict)
        elif method == "trigger_storage_schedule":
            logging.info("trigger_schedule")
            schedule_id = await getattr(client, method)(**call_dict)
            hass.states.async_set(f"{DOMAIN}.schedule_id", schedule_id)
        elif method == "trigger_and_get_schedule":
            logging.info("trigger_schedule")
            schedule = await getattr(client, method)(**call_dict)
            new_state = (
                "ChargeScheduleAvailable" + datetime.now(tz=pytz.utc).isoformat()
            )
            hass.states.async_set(
                f"{DOMAIN}.charge_schedule", new_state=new_state, attributes=schedule
            )
        elif method == "get_schedule":
            logging.info("get schedule")
            schedule = await getattr(client, method)(**call_dict)
            new_state = (
                "ChargeScheduleAvailable" + datetime.now(tz=pytz.utc).isoformat()
            )
            hass.states.async_set(
                f"{DOMAIN}.charge_schedule", new_state=new_state, attributes=schedule
            )

        elif method is not None and hasattr(client, method):
            await getattr(client, method)(**call_dict)

    async def schedule_trigger_event_listener(event):
        state = event.data.get("new_state")

        try:
            _state = state_helper.state_as_number(state)
        except ValueError:
            _state = state.state

        if state.domain != "flexmeasures":
            return

        if state.object_id == "trigger_and_get_schedule":
            schedule = await client.trigger_and_get_schedule(**state.attributes)
            new_state = (
                "ChargeScheduleAvailable" + datetime.now(tz=pytz.utc).isoformat()
            )

            hass.states.async_set(
                f"{DOMAIN}.charge_schedule", new_state=new_state, attributes=schedule
            )

        if state.object_id == "get_sensors":
            sensors = await client.get_sensors(**state.attributes)
            new_state = "sensors"
            hass.states.async_set(
                f"{DOMAIN}.sensors", new_state=new_state, attributes=sensors
            )

        if state.object_id == "post_measurements":
            logging.info("post measurement")
            await client.post_measurements(**state.attributes)

        if state.object_id == "trigger_storage_schedule":
            logging.info("trigger_schedule")
            schedule_id = await client.trigger_storage_schedule(**state.attributes)
            hass.states.async_set(f"{DOMAIN}.schedule_id", schedule_id)
            # hass.states.set("schedule_id", schedule_id)

        if state.object_id == "get_schedule":
            logging.info("get schedule")
            schedule = await client.get_schedule(**state.attributes)
            # hass.states.async_set(f"{DOMAIN}.schedule", new_state=schedule['start'])
            new_state = (
                "ChargeScheduleAvailable" + datetime.now(tz=pytz.utc).isoformat()
            )
            hass.states.async_set(
                f"{DOMAIN}.charge_schedule", new_state=new_state, attributes=schedule
            )

    def handle_s2(call):
        """Handle the service call to the FlexMeasures S2 websockets implementation."""
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        hass.states.set("flexmeasures_s2.message", name)

    # Register services
    hass.services.async_register(DOMAIN, "api", handle_api)
    hass.bus.async_listen(EVENT_STATE_CHANGED, schedule_trigger_event_listener)
    hass.services.async_register(DOMAIN, "s2", handle_s2)
    async_register_s2_api(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Remove services
    hass.services.async_remove(DOMAIN, "api")
    hass.services.async_remove(DOMAIN, "s2")

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
