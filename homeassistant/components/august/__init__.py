"""Support for August devices."""
import asyncio
import itertools
import logging

from august.api import AugustApiHTTPError
from august.authenticator import ValidationResult
from august.doorbell import Doorbell
from august.lock import Lock
from requests import RequestException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import Throttle

from .activity import ActivityStream
from .const import (
    AUGUST_COMPONENTS,
    AUGUST_DEVICE_UPDATE,
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DATA_AUGUST,
    DEFAULT_AUGUST_CONFIG_FILE,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGIN_METHODS,
    MIN_TIME_BETWEEN_DETAIL_UPDATES,
    VERIFICATION_CODE_KEY,
)
from .exceptions import InvalidAuth, RequireValidation
from .gateway import AugustGateway

_LOGGER = logging.getLogger(__name__)

TWO_FA_REVALIDATE = "verify_configurator"

DEFAULT_SCAN_INTERVAL = MIN_TIME_BETWEEN_DETAIL_UPDATES

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_LOGIN_METHOD): vol.In(LOGIN_METHODS),
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_INSTALL_ID): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_request_validation(hass, config_entry, august_gateway):
    """Request a new verification code from the user."""

    #
    # In the future this should start a new config flow
    # instead of using the legacy configurator
    #
    _LOGGER.error("Access token is no longer valid.")
    configurator = hass.components.configurator
    entry_id = config_entry.entry_id

    async def async_august_configuration_validation_callback(data):
        code = data.get(VERIFICATION_CODE_KEY)
        result = await hass.async_add_executor_job(
            august_gateway.authenticator.validate_verification_code, code
        )

        if result == ValidationResult.INVALID_VERIFICATION_CODE:
            configurator.async_notify_errors(
                hass.data[DOMAIN][entry_id][TWO_FA_REVALIDATE],
                "Invalid verification code, please make sure you are using the latest code and try again.",
            )
        elif result == ValidationResult.VALIDATED:
            return await async_setup_august(hass, config_entry, august_gateway)

        return False

    if TWO_FA_REVALIDATE not in hass.data[DOMAIN][entry_id]:
        await hass.async_add_executor_job(
            august_gateway.authenticator.send_verification_code
        )

    entry_data = config_entry.data
    login_method = entry_data.get(CONF_LOGIN_METHOD)
    username = entry_data.get(CONF_USERNAME)

    hass.data[DOMAIN][entry_id][TWO_FA_REVALIDATE] = configurator.async_request_config(
        f"{DEFAULT_NAME} ({username})",
        async_august_configuration_validation_callback,
        description="August must be re-verified. Please check your {} ({}) and enter the verification "
        "code below".format(login_method, username),
        submit_caption="Verify",
        fields=[
            {"id": VERIFICATION_CODE_KEY, "name": "Verification code", "type": "string"}
        ],
    )
    return


async def async_setup_august(hass, config_entry, august_gateway):
    """Set up the August component."""

    entry_id = config_entry.entry_id
    hass.data[DOMAIN].setdefault(entry_id, {})

    try:
        august_gateway.authenticate()
    except RequireValidation:
        await async_request_validation(hass, config_entry, august_gateway)
        return False
    except InvalidAuth:
        _LOGGER.error("Password is no longer valid. Please set up August again")
        return False

    # We still use the configurator to get a new 2fa code
    # when needed since config_flow doesn't have a way
    # to re-request if it expires
    if TWO_FA_REVALIDATE in hass.data[DOMAIN][entry_id]:
        hass.components.configurator.async_request_done(
            hass.data[DOMAIN][entry_id].pop(TWO_FA_REVALIDATE)
        )

    hass.data[DOMAIN][entry_id][DATA_AUGUST] = await hass.async_add_executor_job(
        AugustData, hass, august_gateway
    )
    await hass.data[DOMAIN][entry_id][DATA_AUGUST].activity_stream.async_start()

    for component in AUGUST_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the August component from YAML."""

    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LOGIN_METHOD: conf.get(CONF_LOGIN_METHOD),
                CONF_USERNAME: conf.get(CONF_USERNAME),
                CONF_PASSWORD: conf.get(CONF_PASSWORD),
                CONF_INSTALL_ID: conf.get(CONF_INSTALL_ID),
                CONF_ACCESS_TOKEN_CACHE_FILE: DEFAULT_AUGUST_CONFIG_FILE,
            },
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up August from a config entry."""

    august_gateway = AugustGateway(hass)
    august_gateway.async_setup(entry.data)

    return await async_setup_august(hass, entry, august_gateway)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN][entry.entry_id][DATA_AUGUST].activity_stream.async_stop()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in AUGUST_COMPONENTS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AugustData:
    """August data object."""

    def __init__(self, hass, august_gateway):
        """Init August data object."""
        self._hass = hass
        self._august_gateway = august_gateway
        self._api = august_gateway.api

        self._doorbells = (
            self._api.get_doorbells(self._august_gateway.access_token) or []
        )
        self._locks = (
            self._api.get_operable_locks(self._august_gateway.access_token) or []
        )
        self._house_ids = set()
        for device in itertools.chain(self._doorbells, self._locks):
            self._house_ids.add(device.house_id)

        self._doorbell_detail_by_id = {}
        self._lock_detail_by_id = {}

        # We check the locks right away so we can
        # remove inoperative ones
        self._update_locks_detail()
        self._update_doorbells_detail()
        self._filter_inoperative_locks()

        self.activity_stream = ActivityStream(
            hass, self._api, self._august_gateway, self._house_ids
        )

    @property
    def house_ids(self):
        """Return a list of house_ids."""
        return self._house_ids

    @property
    def doorbells(self):
        """Return a list of doorbells."""
        return self._doorbells

    @property
    def locks(self):
        """Return a list of locks."""
        return self._locks

    async def async_get_device_detail(self, device):
        """Return the detail for a device."""
        if isinstance(device, Lock):
            return await self.async_get_lock_detail(device.device_id)
        if isinstance(device, Doorbell):
            return await self.async_get_doorbell_detail(device.device_id)
        raise ValueError

    async def async_get_doorbell_detail(self, device_id):
        """Return doorbell detail."""
        await self._async_update_doorbells_detail()
        return self._doorbell_detail_by_id.get(device_id)

    @Throttle(MIN_TIME_BETWEEN_DETAIL_UPDATES)
    async def _async_update_doorbells_detail(self):
        await self._hass.async_add_executor_job(self._update_doorbells_detail)

    def _update_doorbells_detail(self):
        self._doorbell_detail_by_id = self._update_device_detail(
            "doorbell", self._doorbells, self._api.get_doorbell_detail
        )

    def lock_has_doorsense(self, device_id):
        """Determine if a lock has doorsense installed and can tell when the door is open or closed."""
        # We do not update here since this is not expected
        # to change until restart
        if self._lock_detail_by_id[device_id] is None:
            return False
        return self._lock_detail_by_id[device_id].doorsense

    async def async_get_lock_detail(self, device_id):
        """Return lock detail."""
        await self._async_update_locks_detail()
        return self._lock_detail_by_id[device_id]

    def get_device_name(self, device_id):
        """Return doorbell or lock name as August has it stored."""
        for device in itertools.chain(self._locks, self._doorbells):
            if device.device_id == device_id:
                return device.device_name

    @Throttle(MIN_TIME_BETWEEN_DETAIL_UPDATES)
    async def _async_update_locks_detail(self):
        await self._hass.async_add_executor_job(self._update_locks_detail)

    def _update_locks_detail(self):
        self._lock_detail_by_id = self._update_device_detail(
            "lock", self._locks, self._api.get_lock_detail
        )

    def _update_device_detail(self, device_type, devices, api_call):
        detail_by_id = {}

        _LOGGER.debug("Start retrieving %s detail", device_type)
        for device in devices:
            device_id = device.device_id
            detail_by_id[device_id] = None
            try:
                detail_by_id[device_id] = api_call(
                    self._august_gateway.access_token, device_id
                )
            except RequestException as ex:
                _LOGGER.error(
                    "Request error trying to retrieve %s details for %s. %s",
                    device_type,
                    device.device_name,
                    ex,
                )

        _LOGGER.debug("Completed retrieving %s detail", device_type)
        return detail_by_id

    async def async_signal_operation_changed_device_state(self, device_id):
        """Signal a device update when an operation changes state."""
        _LOGGER.debug(
            "async_dispatcher_send (from operation): AUGUST_DEVICE_UPDATE-%s", device_id
        )
        async_dispatcher_send(self._hass, f"{AUGUST_DEVICE_UPDATE}-{device_id}")

    def lock(self, device_id):
        """Lock the device."""
        return self._call_api_op_requires_bridge(
            device_id,
            self._api.lock_return_activities,
            self._august_gateway.access_token,
            device_id,
        )

    def unlock(self, device_id):
        """Unlock the device."""
        return self._call_api_op_requires_bridge(
            device_id,
            self._api.unlock_return_activities,
            self._august_gateway.access_token,
            device_id,
        )

    def _call_api_op_requires_bridge(self, device_id, func, *args, **kwargs):
        """Call an API that requires the bridge to be online and will change the device state."""
        ret = None
        try:
            ret = func(*args, **kwargs)
        except AugustApiHTTPError as err:
            device_name = self.get_device_name(device_id)
            if device_name is None:
                device_name = f"DeviceID: {device_id}"
            raise HomeAssistantError(f"{device_name}: {err}")

        return ret

    def _filter_inoperative_locks(self):
        # Remove non-operative locks as there must
        # be a bridge (August Connect) for them to
        # be usable
        operative_locks = []
        for lock in self._locks:
            lock_detail = self._lock_detail_by_id.get(lock.device_id)
            if lock_detail is None:
                _LOGGER.info(
                    "The lock %s could not be setup because the system could not fetch details about the lock.",
                    lock.device_name,
                )
            elif lock_detail.bridge is None:
                _LOGGER.info(
                    "The lock %s could not be setup because it does not have a bridge (Connect).",
                    lock.device_name,
                )
            elif not lock_detail.bridge.operative:
                _LOGGER.info(
                    "The lock %s could not be setup because the bridge (Connect) is not operative.",
                    lock.device_name,
                )
            else:
                operative_locks.append(lock)

        self._locks = operative_locks
