"""Handle forward of events transmitted by Hue devices to HASS."""
import logging
from typing import TYPE_CHECKING

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.button import Button

from homeassistant.const import CONF_DEVICE_ID, CONF_ID, CONF_TYPE, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.helpers import device_registry
from homeassistant.util import slugify

from ..const import ATTR_HUE_EVENT, CONF_SUBTYPE, DOMAIN as DOMAIN

CONF_CONTROL_ID = "control_id"

if TYPE_CHECKING:
    from ..bridge import HueBridge

LOGGER = logging.getLogger(__name__)


async def async_setup_hue_events(bridge: "HueBridge"):
    """Manage listeners for stateless Hue sensors that emit events."""
    hass = bridge.hass
    api: HueBridgeV2 = bridge.api  # to satisfy typing
    conf_entry = bridge.config_entry
    dev_reg = device_registry.async_get(hass)

    # at this time the `button` resource is the only source of hue events
    btn_controller = api.sensors.button

    @callback
    def handle_button_event(evt_type: EventType, hue_resource: Button) -> None:
        """Handle event from Hue devices controller."""
        LOGGER.debug("Received button event: %s", hue_resource)
        hue_device = btn_controller.get_device(hue_resource.id)
        device = dev_reg.async_get_device({(DOMAIN, hue_device.id)})

        # Fire event
        data = {
            # send slugified entity name as id = backwards compatibility with previous version
            CONF_ID: slugify(f"{hue_device.metadata.name}: Button"),
            CONF_DEVICE_ID: device.id,  # type: ignore
            CONF_UNIQUE_ID: hue_resource.id,
            CONF_TYPE: hue_resource.button.last_event.value,
            CONF_SUBTYPE: hue_resource.metadata.control_id,
        }
        hass.bus.async_fire(ATTR_HUE_EVENT, data)

    # add listener for updates from `button` resource
    conf_entry.async_on_unload(
        btn_controller.subscribe(
            handle_button_event, event_filter=EventType.RESOURCE_UPDATED
        )
    )
