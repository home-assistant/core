"""Support for August devices."""
import asyncio
import itertools
import logging

from aiohttp import ClientError, ClientResponseError
from august.authenticator import ValidationResult
from august.exceptions import AugustApiAIOHTTPError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    HTTP_UNAUTHORIZED,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .activity import ActivityStream
from .const import (
    AUGUST_COMPONENTS,
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
from .exceptions import CannotConnect, InvalidAuth, RequireValidation
from .gateway import AugustGateway
from .subscriber import AugustSubscriberMixin

_LOGGER = logging.getLogger(__name__)

TWO_FA_REVALIDATE = "verify_configurator"

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
    _LOGGER.error("Access token is no longer valid")
    configurator = hass.components.configurator
    entry_id = config_entry.entry_id

    async def async_august_configuration_validation_callback(data):
        code = data.get(VERIFICATION_CODE_KEY)
        result = await august_gateway.authenticator.async_validate_verification_code(
            code
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
        await august_gateway.authenticator.async_send_verification_code()

    entry_data = config_entry.data
    login_method = entry_data.get(CONF_LOGIN_METHOD)
    username = entry_data.get(CONF_USERNAME)

    hass.data[DOMAIN][entry_id][TWO_FA_REVALIDATE] = configurator.async_request_config(
        f"{DEFAULT_NAME} ({username})",
        async_august_configuration_validation_callback,
        description=(
            "August must be re-verified. "
            f"Please check your {login_method} ({username}) "
            "and enter the verification code below"
        ),
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
        await august_gateway.async_authenticate()
    except RequireValidation:
        await async_request_validation(hass, config_entry, august_gateway)
        raise

    # We still use the configurator to get a new 2fa code
    # when needed since config_flow doesn't have a way
    # to re-request if it expires
    if TWO_FA_REVALIDATE in hass.data[DOMAIN][entry_id]:
        hass.components.configurator.async_request_done(
            hass.data[DOMAIN][entry_id].pop(TWO_FA_REVALIDATE)
        )

    hass.data[DOMAIN][entry_id][DATA_AUGUST] = AugustData(hass, august_gateway)

    await hass.data[DOMAIN][entry_id][DATA_AUGUST].async_setup()

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

    try:
        await august_gateway.async_setup(entry.data)
        return await async_setup_august(hass, entry, august_gateway)
    except ClientResponseError as err:
        if err.status == HTTP_UNAUTHORIZED:
            _async_start_reauth(hass, entry)
            return False

        raise ConfigEntryNotReady from err
    except InvalidAuth:
        _async_start_reauth(hass, entry)
        return False
    except RequireValidation:
        return False
    except (CannotConnect, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady from err


def _async_start_reauth(hass: HomeAssistant, entry: ConfigEntry):
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth"},
            data=entry.data,
        )
    )
    _LOGGER.error("Password is no longer valid. Please reauthenticate")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
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


class AugustData(AugustSubscriberMixin):
    """August data object."""

    def __init__(self, hass, august_gateway):
        """Init August data object."""
        super().__init__(hass, MIN_TIME_BETWEEN_DETAIL_UPDATES)
        self._hass = hass
        self._august_gateway = august_gateway
        self.activity_stream = None
        self._api = august_gateway.api
        self._device_detail_by_id = {}
        self._doorbells_by_id = {}
        self._locks_by_id = {}
        self._house_ids = set()

    async def async_setup(self):
        """Async setup of august device data and activities."""
        locks = (
            await self._api.async_get_operable_locks(self._august_gateway.access_token)
            or []
        )
        doorbells = (
            await self._api.async_get_doorbells(self._august_gateway.access_token) or []
        )

        self._doorbells_by_id = {device.device_id: device for device in doorbells}
        self._locks_by_id = {device.device_id: device for device in locks}
        self._house_ids = {
            device.house_id for device in itertools.chain(locks, doorbells)
        }

        await self._async_refresh_device_detail_by_ids(
            [device.device_id for device in itertools.chain(locks, doorbells)]
        )

        # We remove all devices that we are missing
        # detail as we cannot determine if they are usable.
        # This also allows us to avoid checking for
        # detail being None all over the place
        self._remove_inoperative_locks()
        self._remove_inoperative_doorbells()

        self.activity_stream = ActivityStream(
            self._hass, self._api, self._august_gateway, self._house_ids
        )
        await self.activity_stream.async_setup()

    @property
    def doorbells(self):
        """Return a list of py-august Doorbell objects."""
        return self._doorbells_by_id.values()

    @property
    def locks(self):
        """Return a list of py-august Lock objects."""
        return self._locks_by_id.values()

    def get_device_detail(self, device_id):
        """Return the py-august LockDetail or DoorbellDetail object for a device."""
        return self._device_detail_by_id[device_id]

    async def _async_refresh(self, time):
        await self._async_refresh_device_detail_by_ids(self._subscriptions.keys())

    async def _async_refresh_device_detail_by_ids(self, device_ids_list):
        for device_id in device_ids_list:
            if device_id in self._locks_by_id:
                await self._async_update_device_detail(
                    self._locks_by_id[device_id], self._api.async_get_lock_detail
                )
                # keypads are always attached to locks
                if (
                    device_id in self._device_detail_by_id
                    and self._device_detail_by_id[device_id].keypad is not None
                ):
                    keypad = self._device_detail_by_id[device_id].keypad
                    self._device_detail_by_id[keypad.device_id] = keypad
            elif device_id in self._doorbells_by_id:
                await self._async_update_device_detail(
                    self._doorbells_by_id[device_id],
                    self._api.async_get_doorbell_detail,
                )
            _LOGGER.debug(
                "async_signal_device_id_update (from detail updates): %s", device_id
            )
            self.async_signal_device_id_update(device_id)

    async def _async_update_device_detail(self, device, api_call):
        _LOGGER.debug(
            "Started retrieving detail for %s (%s)",
            device.device_name,
            device.device_id,
        )

        try:
            self._device_detail_by_id[device.device_id] = await api_call(
                self._august_gateway.access_token, device.device_id
            )
        except ClientError as ex:
            _LOGGER.error(
                "Request error trying to retrieve %s details for %s. %s",
                device.device_id,
                device.device_name,
                ex,
            )
        _LOGGER.debug(
            "Completed retrieving detail for %s (%s)",
            device.device_name,
            device.device_id,
        )

    def _get_device_name(self, device_id):
        """Return doorbell or lock name as August has it stored."""
        if self._locks_by_id.get(device_id):
            return self._locks_by_id[device_id].device_name
        if self._doorbells_by_id.get(device_id):
            return self._doorbells_by_id[device_id].device_name

    async def async_lock(self, device_id):
        """Lock the device."""
        return await self._async_call_api_op_requires_bridge(
            device_id,
            self._api.async_lock_return_activities,
            self._august_gateway.access_token,
            device_id,
        )

    async def async_unlock(self, device_id):
        """Unlock the device."""
        return await self._async_call_api_op_requires_bridge(
            device_id,
            self._api.async_unlock_return_activities,
            self._august_gateway.access_token,
            device_id,
        )

    async def _async_call_api_op_requires_bridge(
        self, device_id, func, *args, **kwargs
    ):
        """Call an API that requires the bridge to be online and will change the device state."""
        ret = None
        try:
            ret = await func(*args, **kwargs)
        except AugustApiAIOHTTPError as err:
            device_name = self._get_device_name(device_id)
            if device_name is None:
                device_name = f"DeviceID: {device_id}"
            raise HomeAssistantError(f"{device_name}: {err}") from err

        return ret

    def _remove_inoperative_doorbells(self):
        doorbells = list(self.doorbells)
        for doorbell in doorbells:
            device_id = doorbell.device_id
            doorbell_is_operative = False
            doorbell_detail = self._device_detail_by_id.get(device_id)
            if doorbell_detail is None:
                _LOGGER.info(
                    "The doorbell %s could not be setup because the system could not fetch details about the doorbell",
                    doorbell.device_name,
                )
            else:
                doorbell_is_operative = True

            if not doorbell_is_operative:
                del self._doorbells_by_id[device_id]
                del self._device_detail_by_id[device_id]

    def _remove_inoperative_locks(self):
        # Remove non-operative locks as there must
        # be a bridge (August Connect) for them to
        # be usable
        locks = list(self.locks)

        for lock in locks:
            device_id = lock.device_id
            lock_is_operative = False
            lock_detail = self._device_detail_by_id.get(device_id)
            if lock_detail is None:
                _LOGGER.info(
                    "The lock %s could not be setup because the system could not fetch details about the lock",
                    lock.device_name,
                )
            elif lock_detail.bridge is None:
                _LOGGER.info(
                    "The lock %s could not be setup because it does not have a bridge (Connect)",
                    lock.device_name,
                )
            elif not lock_detail.bridge.operative:
                _LOGGER.info(
                    "The lock %s could not be setup because the bridge (Connect) is not operative",
                    lock.device_name,
                )
            else:
                lock_is_operative = True

            if not lock_is_operative:
                del self._locks_by_id[device_id]
                del self._device_detail_by_id[device_id]
