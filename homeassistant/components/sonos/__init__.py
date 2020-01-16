"""Support to embed Sonos."""
import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOSTS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

CONF_ADVERTISE_ADDR = "advertise_addr"
CONF_INTERFACE_ADDR = "interface_addr"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                MP_DOMAIN: vol.Schema(
                    {
                        vol.Optional(CONF_ADVERTISE_ADDR): cv.string,
                        vol.Optional(CONF_INTERFACE_ADDR): cv.string,
                        vol.Optional(CONF_HOSTS): vol.All(
                            cv.ensure_list_csv, [cv.string]
                        ),
                    }
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"
SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_UPDATE_ALARM = "update_alarm"
SERVICE_SET_OPTION = "set_option"
SERVICE_PLAY_QUEUE = "play_queue"

ATTR_SLEEP_TIME = "sleep_time"
ATTR_ALARM_ID = "alarm_id"
ATTR_VOLUME = "volume"
ATTR_ENABLED = "enabled"
ATTR_INCLUDE_LINKED_ZONES = "include_linked_zones"
ATTR_MASTER = "master"
ATTR_WITH_GROUP = "with_group"
ATTR_NIGHT_SOUND = "night_sound"
ATTR_SPEECH_ENHANCE = "speech_enhance"
ATTR_QUEUE_POSITION = "queue_position"

SONOS_JOIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MASTER): cv.entity_id,
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    }
)

SONOS_UNJOIN_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids})

SONOS_STATES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Optional(ATTR_WITH_GROUP, default=True): cv.boolean,
    }
)


DATA_SERVICE_EVENT = "sonos_service_idle"


async def async_setup(hass, config):
    """Set up the Sonos component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = conf or {}
    hass.data[DATA_SERVICE_EVENT] = asyncio.Event()

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    async def service_handle(service):
        """Dispatch a service call."""
        hass.data[DATA_SERVICE_EVENT].clear()
        async_dispatcher_send(hass, DOMAIN, service.service, service.data)
        await hass.data[DATA_SERVICE_EVENT].wait()

    hass.services.async_register(
        DOMAIN, SERVICE_JOIN, service_handle, schema=SONOS_JOIN_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_UNJOIN, service_handle, schema=SONOS_UNJOIN_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SNAPSHOT, service_handle, schema=SONOS_STATES_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE, service_handle, schema=SONOS_STATES_SCHEMA
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up Sonos from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )

    return True
