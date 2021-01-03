"""Support for Sure Petcare cat/pet flaps."""
import logging
from typing import Any, Dict, List

from surepy import (
    MESTART_RESOURCE,
    SureLockStateID,
    SurePetcare,
    SurePetcareAuthenticationError,
    SurePetcareError,
    SurepyProduct,
)
import voluptuous as vol

from homeassistant.const import (
    CONF_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCK_STATE,
    CONF_FEEDERS,
    CONF_FLAPS,
    CONF_PARENT,
    CONF_PETS,
    CONF_PRODUCT_ID,
    DATA_SURE_PETCARE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SPC,
    SURE_API_TIMEOUT,
    TOPIC_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_FEEDERS, default=[]): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_FLAPS, default=[]): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_PETS): vol.All(cv.ensure_list, [cv.positive_int]),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config) -> bool:
    """Initialize the Sure Petcare component."""
    conf = config[DOMAIN]

    # update interval
    scan_interval = conf[CONF_SCAN_INTERVAL]

    # shared data
    hass.data[DOMAIN] = hass.data[DATA_SURE_PETCARE] = {}

    # sure petcare api connection
    try:
        surepy = SurePetcare(
            conf[CONF_USERNAME],
            conf[CONF_PASSWORD],
            hass.loop,
            async_get_clientsession(hass),
            api_timeout=SURE_API_TIMEOUT,
        )

    except SurePetcareAuthenticationError:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        return False
    except SurePetcareError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong %s!", error)
        return False

    # add feeders
    things = [
        {CONF_ID: feeder, CONF_TYPE: SurepyProduct.FEEDER}
        for feeder in conf[CONF_FEEDERS]
    ]

    # add flaps (don't differentiate between CAT and PET for now)
    things.extend(
        [
            {CONF_ID: flap, CONF_TYPE: SurepyProduct.PET_FLAP}
            for flap in conf[CONF_FLAPS]
        ]
    )

    # discover hubs the flaps/feeders are connected to
    hub_ids = set()
    for device in things.copy():
        device_data = await surepy.device(device[CONF_ID])
        if (
            CONF_PARENT in device_data
            and device_data[CONF_PARENT][CONF_PRODUCT_ID] == SurepyProduct.HUB
            and device_data[CONF_PARENT][CONF_ID] not in hub_ids
        ):
            things.append(
                {
                    CONF_ID: device_data[CONF_PARENT][CONF_ID],
                    CONF_TYPE: SurepyProduct.HUB,
                }
            )
            hub_ids.add(device_data[CONF_PARENT][CONF_ID])

    # add pets
    things.extend(
        [{CONF_ID: pet, CONF_TYPE: SurepyProduct.PET} for pet in conf[CONF_PETS]]
    )

    _LOGGER.debug("Devices and Pets to setup: %s", things)

    spc = hass.data[DATA_SURE_PETCARE][SPC] = SurePetcareAPI(hass, surepy, things)

    # initial update
    await spc.async_update()

    async_track_time_interval(hass, spc.async_update, scan_interval)

    # load platforms
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("binary_sensor", DOMAIN, {}, config)
    )
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, {}, config)
    )

    async def handle_set_lock_state(call):
        """Call when setting the lock state."""
        await spc.set_lock_state(call.data[ATTR_FLAP_ID], call.data[ATTR_LOCK_STATE])
        await spc.async_update()

    lock_state_service_schema = vol.Schema(
        {
            vol.Required(ATTR_FLAP_ID): vol.All(
                cv.positive_int, vol.In(conf[CONF_FLAPS])
            ),
            vol.Required(ATTR_LOCK_STATE): vol.All(
                cv.string,
                vol.Lower,
                vol.In(
                    [
                        SureLockStateID.UNLOCKED.name.lower(),
                        SureLockStateID.LOCKED_IN.name.lower(),
                        SureLockStateID.LOCKED_OUT.name.lower(),
                        SureLockStateID.LOCKED_ALL.name.lower(),
                    ]
                ),
            ),
        }
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LOCK_STATE,
        handle_set_lock_state,
        schema=lock_state_service_schema,
    )

    return True


class SurePetcareAPI:
    """Define a generic Sure Petcare object."""

    def __init__(self, hass, surepy: SurePetcare, ids: List[Dict[str, Any]]) -> None:
        """Initialize the Sure Petcare object."""
        self.hass = hass
        self.surepy = surepy
        self.ids = ids
        self.states: Dict[str, Any] = {}

    async def async_update(self, arg: Any = None) -> None:
        """Refresh Sure Petcare data."""

        # Fetch all data from SurePet API, refreshing the surepy cache
        # TODO: get surepy upstream to add a method to clear the cache explicitly pylint: disable=fixme
        await self.surepy._get_resource(  # pylint: disable=protected-access
            resource=MESTART_RESOURCE
        )
        for thing in self.ids:
            sure_id = thing[CONF_ID]
            sure_type = thing[CONF_TYPE]

            try:
                type_state = self.states.setdefault(sure_type, {})

                if sure_type in [
                    SurepyProduct.CAT_FLAP,
                    SurepyProduct.PET_FLAP,
                    SurepyProduct.FEEDER,
                    SurepyProduct.HUB,
                ]:
                    type_state[sure_id] = await self.surepy.device(sure_id)
                elif sure_type == SurepyProduct.PET:
                    type_state[sure_id] = await self.surepy.pet(sure_id)

            except SurePetcareError as error:
                _LOGGER.error("Unable to retrieve data from surepetcare.io: %s", error)

        async_dispatcher_send(self.hass, TOPIC_UPDATE)

    async def set_lock_state(self, flap_id: int, state: str) -> None:
        """Update the lock state of a flap."""
        if state == SureLockStateID.UNLOCKED.name.lower():
            await self.surepy.unlock(flap_id)
        elif state == SureLockStateID.LOCKED_IN.name.lower():
            await self.surepy.lock_in(flap_id)
        elif state == SureLockStateID.LOCKED_OUT.name.lower():
            await self.surepy.lock_out(flap_id)
        elif state == SureLockStateID.LOCKED_ALL.name.lower():
            await self.surepy.lock(flap_id)
