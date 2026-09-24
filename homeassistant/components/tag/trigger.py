"""Support for tag triggers."""

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DEVICE_ID, DOMAIN, EVENT_TAG_SCANNED, TAG_ID

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(TAG_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for tag_scanned events based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    tag_ids: set[str] = set(config[TAG_ID])
    device_ids: set[str] | None = (
        set(config[DEVICE_ID]) if DEVICE_ID in config else None
    )
    if device_ids is not None:
        device_registry = dr.async_get(hass)
        # A pre-migration composite device id no longer refers to a registered device;
        # a tag scanned event carries the id of one of the devices it was split into.
        # Expand it to those split device ids so the trigger keeps matching.
        for device_id in list(device_ids):
            split_devices = device_registry.async_get_devices_for_composite_device_id(
                device_id
            )
            if split_devices:
                device_ids.discard(device_id)
                device_ids.update(split_device.id for split_device in split_devices)

    job = HassJob(action)

    async def handle_event(event: Event) -> None:
        """Listen for tag scan events and calls the action when data matches."""
        if event.data.get(TAG_ID) not in tag_ids or (
            device_ids is not None and event.data.get(DEVICE_ID) not in device_ids
        ):
            return

        task = hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": DOMAIN,
                    "event": event,
                    "description": "Tag scanned",
                }
            },
            event.context,
        )

        if task:
            await task

    return hass.bus.async_listen(EVENT_TAG_SCANNED, handle_event)
