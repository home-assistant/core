"""iCloud account."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
import logging
import operator
from typing import TYPE_CHECKING, Any

from pyicloud import PyiCloudService
from pyicloud.const import AppleAuthError
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloudAcceptTermsException,
    PyiCloudAPIResponseException,
    PyiCloudAuthRequiredException,
    PyiCloudConnectionException,
    PyiCloudFailedLoginException,
    PyiCloudNoDevicesException,
    PyiCloudServiceNotActivatedException,
    PyiCloudServiceUnavailable,
)
from pyicloud.services.findmyiphone import AppleDevice

from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_USERNAME, EntityStateAttribute
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.dt import as_utc, parse_datetime, utcnow
from homeassistant.util.location import distance

from .const import (
    ATTR_ACCOUNT_FETCH_INTERVAL,
    ATTR_BATTERY,
    ATTR_BATTERY_STATUS,
    ATTR_DEVICE_NAME,
    ATTR_DEVICE_STATUS,
    ATTR_LOW_POWER_MODE,
    ATTR_OWNER_NAME,
    DEVICE_ACTION_STATUS_CODE,
    DEVICE_ACTION_STATUS_PENDING,
    DEVICE_ACTIVATION_LOCKED,
    DEVICE_BATTERY_LEVEL,
    DEVICE_BATTERY_STATUS,
    DEVICE_CLASS,
    DEVICE_DISPLAY_NAME,
    DEVICE_FEATURE_LOCK,
    DEVICE_FEATURES,
    DEVICE_ID,
    DEVICE_IS_LOCATING,
    DEVICE_LOCATION,
    DEVICE_LOCATION_ALTITUDE,
    DEVICE_LOCATION_ENABLED,
    DEVICE_LOCATION_FLOOR_LEVEL,
    DEVICE_LOCATION_HORIZONTAL_ACCURACY,
    DEVICE_LOCATION_IS_INACCURATE,
    DEVICE_LOCATION_IS_OLD,
    DEVICE_LOCATION_LATITUDE,
    DEVICE_LOCATION_LONGITUDE,
    DEVICE_LOCATION_POSITION_TYPE,
    DEVICE_LOCATION_TIMESTAMP,
    DEVICE_LOCKED_TIMESTAMP,
    DEVICE_LOST_MODE_CAPABLE,
    DEVICE_LOST_MODE_ENABLED,
    DEVICE_LOST_TIMESTAMP,
    DEVICE_LOW_POWER_MODE,
    DEVICE_NAME,
    DEVICE_PERSON_ID,
    DEVICE_RAW_DEVICE_MODEL,
    DEVICE_REMOTE_LOCK,
    DEVICE_STATUS,
    DEVICE_STATUS_CODES,
    DEVICE_STATUS_SET,
    DEVICE_WIPE_IN_PROGRESS,
    DEVICE_WIPED_TIMESTAMP,
    DOMAIN,
)

if TYPE_CHECKING:
    from .coordinator import IcloudCalendarCoordinator, IcloudRemindersCoordinator
    from .media_source import PhotoCache

_LOGGER = logging.getLogger(__name__)

# pyicloud only raises PyiCloud2FARequiredException for a 409 whose body is JSON
# with authType == "hsa2". Every other authentication rejection falls through to
# Session._raise_error(), which raises a plain PyiCloudAPIResponseException
# carrying the HTTP status in .code, so the status is what has to be inspected.
#
# GENERAL_AUTH_ERROR (500) is excluded on purpose: pyicloud groups it with the
# authentication statuses, but a 500 is just as likely to be a transient iCloud
# failure, and those have to keep being retried rather than parked for the user.
_AUTH_REQUIRED_STATUSES = frozenset(
    {
        AppleAuthError.TWO_FACTOR_REQUIRED,
        AppleAuthError.LOGIN_TOKEN_EXPIRED,
        AppleAuthError.FIND_MY_REAUTH_REQUIRED,
    }
)


def is_auth_error(err: PyiCloudAPIResponseException) -> bool:
    """Return True if the account has to authenticate again to recover."""
    return isinstance(err.code, int) and err.code in _AUTH_REQUIRED_STATUSES


def _is_usable_location(location: dict[str, Any] | None) -> bool:
    """Return whether a location carries everything the tracker reads."""
    return location is not None and all(
        location.get(key) is not None
        for key in (
            DEVICE_LOCATION_LATITUDE,
            DEVICE_LOCATION_LONGITUDE,
            DEVICE_LOCATION_HORIZONTAL_ACCURACY,
        )
    )


def _is_auth_failure(err: BaseException) -> bool:
    """Return True if iCloud rejected the session rather than the request."""
    if isinstance(
        err,
        (
            PyiCloud2FARequiredException,
            PyiCloudFailedLoginException,
            PyiCloudAuthRequiredException,
        ),
    ):
        return True
    return isinstance(err, PyiCloudAPIResponseException) and is_auth_error(err)


def is_2fa_status(err: PyiCloudAPIResponseException) -> bool:
    """Return True if the status reports a challenge rather than a rejection.

    The same challenge reaches us either as PyiCloud2FARequiredException or,
    when the body is not the hsa2 JSON pyicloud looks for, as this status on a
    plain response. Both mean a verification code is what is missing.
    """
    return err.code == AppleAuthError.TWO_FACTOR_REQUIRED


def code_can_be_delivered(api: PyiCloudService | None) -> bool:
    """Return whether iCloud has a route to send a verification code.

    The options fetch that sets a route up can be refused on its own, which
    leaves a challenge nothing can act on: no code is sent, and the reauth
    flow would strand the user on a form they cannot complete. pyicloud
    reports "unknown" for exactly that state.
    """
    return api is not None and api.two_factor_delivery_method != "unknown"


type IcloudConfigEntry = ConfigEntry[IcloudAccount]


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an iCloud timestamp.

    iCloud reports timestamps either as epoch milliseconds or as a string,
    and uses ``None`` or an empty string when the event never happened.
    """
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        try:
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        except OSError, OverflowError, ValueError:
            return None

    if isinstance(value, str):
        if (parsed := parse_datetime(value)) is None:
            return None
        return as_utc(parsed)

    return None


def _cannot_connect(err: PyiCloudConnectionException) -> ConfigEntryNotReady:
    """Return the error that has Home Assistant retry an unreachable iCloud."""
    return ConfigEntryNotReady(
        translation_domain=DOMAIN,
        translation_key="cannot_connect",
        translation_placeholders={"error": str(err)},
    )


class IcloudAccount:
    """Representation of an iCloud account."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        icloud_dir: Store,
        with_family: bool,
        max_interval: int,
        gps_accuracy_threshold: int,
        config_entry: IcloudConfigEntry,
    ) -> None:
        """Initialize an iCloud account."""
        self.hass = hass
        self._username = username
        self._password = password
        self._with_family = with_family
        self._fetch_interval: float = max_interval
        self._max_interval = max_interval
        self._gps_accuracy_threshold = gps_accuracy_threshold

        self._icloud_dir = icloud_dir

        self.api: PyiCloudService | None = None
        # Read by the reauth flow when api.requires_2fa cannot be trusted.
        self.requires_verification_code = False
        self._owner_fullname: str | None = None
        self._family_members_fullname: dict[str, str] = {}
        self._devices: dict[str, IcloudDevice] = {}
        self._retried_fetch = False
        self._config_entry = config_entry

        self._unsub_fetch: CALLBACK_TYPE | None = None
        self.listeners: list[CALLBACK_TYPE] = []

        # Built in async_setup_entry, before the platforms are forwarded.
        self.calendar_coordinator: IcloudCalendarCoordinator | None = None
        self.reminders_coordinator: IcloudRemindersCoordinator | None = None

        self.photo_cache: PhotoCache | None = None

    def setup(self) -> None:
        """Set up an iCloud account, leaving it with a fetch scheduled.

        Every path out of _setup() has to end with a timer, including the ones
        that return before update_devices() arms it.
        """
        try:
            self._setup()
        except PyiCloudAPIResponseException as err:
            if not is_auth_error(err):
                raise
            self._ask_to_authenticate(err)
        except (
            PyiCloud2FARequiredException,
            PyiCloudFailedLoginException,
            PyiCloudAuthRequiredException,
            PyiCloudAcceptTermsException,
        ) as err:
            # Refreshing the devices can reject a session that logging in
            # accepted. The entry still loads: the user is asked to act on it,
            # and the timer below keeps polling so it recovers once they have.
            self._ask_to_authenticate(err)

        if self._unsub_fetch is None:
            self._fetch_interval = self._max_interval
            self._schedule_next_fetch()

    def _setup(self) -> None:
        """Log in and read the account's devices."""
        try:
            self.api = PyiCloudService(
                self._username,
                self._password,
                self._icloud_dir.path,
                with_family=self._with_family,
                refresh_interval=None,
            )

        except PyiCloudConnectionException as err:
            # iCloud is unreachable; this says nothing about the credentials, so
            # let the config entry retry instead of asking the user to log in.
            raise _cannot_connect(err) from err

        except PyiCloudFailedLoginException:
            # PyiCloudService authenticates while constructing, so this means
            # the stored password was rejected.
            self._handle_auth_required(two_factor=False, keep_session=False)
            return

        except PyiCloud2FARequiredException:
            # A 2FA challenge can also surface as an exception here rather than
            # as requires_2fa, because authenticate() raises out of
            # _get_mfa_auth_options() before the flag is set. self.api was
            # never assigned either way, so there is no session for the reauth
            # flow to send a code through; ask for the password, which starts a
            # fresh login and re-issues the challenge.
            self._handle_auth_required(two_factor=True, keep_session=False)
            return

        except PyiCloudAuthRequiredException:
            # iCloud rejected the session rather than issuing a challenge, so
            # this is a login to redo, not a code to enter.
            self._handle_auth_required(two_factor=False, keep_session=False)
            return

        except PyiCloudAPIResponseException as err:
            if not is_auth_error(err):
                # Anything else is iCloud failing rather than refusing, so let
                # Home Assistant retry the setup with its own backoff.
                raise ConfigEntryNotReady from err
            # self.api was never assigned, so there is no session to send a
            # code through even when the status asks for one.
            self._handle_auth_required(
                two_factor=is_2fa_status(err), keep_session=False
            )
            return

        if self.api.requires_2fa:
            if not code_can_be_delivered(self.api):
                # Nothing for the user to act on, so retry rather than ask for
                # a code that cannot be sent.
                raise ConfigEntryNotReady(
                    "iCloud asked for a verification code but has no way to send one"
                )
            self._handle_auth_required(two_factor=True, keep_session=True)
            return

        try:
            # Gets device owners infos
            user_info = self.api.devices.user_info
        except PyiCloud2FARequiredException as err:
            # iCloud issues the challenge when the session is refreshed to read
            # the devices rather than while logging in, and does not set
            # requires_2fa for it, so ask for a code explicitly. The session is
            # kept so the reauth flow can send the code through it.
            if not code_can_be_delivered(self.api):
                # Nothing for the user to act on, so retry rather than ask for
                # a code that cannot be sent.
                raise ConfigEntryNotReady from err
            self._handle_auth_required(
                two_factor=True, keep_session=True, start_reauth=False
            )
            raise ConfigEntryAuthFailed from err
        except (PyiCloudFailedLoginException, PyiCloudAuthRequiredException) as err:
            # Reading the devices refreshes the session, and a stored token
            # that iCloud has since invalidated is only rejected here, not
            # while logging in. Only the user can resolve it, so this fails
            # setup as an authentication failure rather than something to
            # retry: Home Assistant starts the reauth flow and stops
            # re-attempting a login that cannot succeed until they are done.
            challenged = self.api is not None and self.api.requires_2fa
            self._handle_auth_required(
                two_factor=challenged, keep_session=challenged, start_reauth=False
            )
            raise ConfigEntryAuthFailed from err
        except PyiCloudConnectionException as err:
            raise _cannot_connect(err) from err
        except (
            PyiCloudServiceNotActivatedException,
            PyiCloudNoDevicesException,
            PyiCloudServiceUnavailable,
        ) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="no_device_found"
            ) from err
        except PyiCloudAPIResponseException as err:
            # Has to stay below the clause above: PyiCloudServiceNotActivatedException
            # is a subclass of this one and would otherwise never be reached.
            if not is_auth_error(err):
                # Anything else is iCloud failing rather than refusing, so let
                # Home Assistant retry the setup with its own backoff.
                raise ConfigEntryNotReady from err
            # A challenge keeps its session for the code to go through. The
            # rejections do not: the session has just failed to refresh, so a
            # reauth flow sending a code through it would fail as well.
            challenge = is_2fa_status(err)
            if challenge and not code_can_be_delivered(self.api):
                # Nothing for the user to act on, so retry rather than ask for
                # a code that cannot be sent.
                raise ConfigEntryNotReady from err
            self._handle_auth_required(
                two_factor=challenge, keep_session=challenge, start_reauth=False
            )
            raise ConfigEntryAuthFailed from err

        if user_info is None:
            raise ConfigEntryNotReady("No user info found in iCloud devices response")

        self._read_account_names(user_info)

        self._devices = {}
        # The FindMyiPhoneServiceManager constructor just located every device,
        # so the first update should only read that fresh data, not request a
        # second active locate from Apple.
        self.update_devices(locate=False)

    def _read_account_names(self, user_info: Mapping[str, Any]) -> None:
        """Store the account owner and family member names."""
        self._owner_fullname = (
            f"{user_info.get('firstName')} {user_info.get('lastName')}"
        )

        self._family_members_fullname = {}
        members_info = user_info.get("membersInfo")
        if members_info is not None:
            for prs_id, member in members_info.items():
                self._family_members_fullname[prs_id] = (
                    f"{member['firstName']} {member['lastName']}"
                )

    def _handle_auth_required(
        self, *, two_factor: bool, keep_session: bool, start_reauth: bool = True
    ) -> None:
        """Report why authentication failed and start the reauth flow.

        two_factor says what iCloud asked for, keep_session whether there is a
        session to ask through: a 2FA challenge raised before the session was
        established leaves nothing to send a code over, so the user has to log
        in again even though a code is what iCloud wants.

        start_reauth is for callers that raise ConfigEntryAuthFailed, which
        starts the flow itself.
        """
        if not keep_session:
            # Without a session the reauth flow goes to the password form,
            # which starts a fresh login and re-issues any challenge.
            self.api = None

        if two_factor and keep_session:
            _LOGGER.warning(
                (
                    "2FA authentication required for '%s'; go to the Integrations "
                    "menu and click on Configure on the discovered Apple iCloud "
                    "card to enter your verification code"
                ),
                self._config_entry.data[CONF_USERNAME],
            )
        elif two_factor:
            _LOGGER.warning(
                (
                    "2FA authentication required for '%s'; go to the Integrations "
                    "menu and click on Configure on the discovered Apple iCloud "
                    "card to login again"
                ),
                self._config_entry.data[CONF_USERNAME],
            )
        else:
            _LOGGER.error(
                (
                    "Your iCloud account for '%s' is no longer working; Go to the "
                    "Integrations menu and click on Configure on the discovered Apple "
                    "iCloud card to login again"
                ),
                self._config_entry.data[CONF_USERNAME],
            )

        # A challenge raised by a request pyicloud does not route through
        # authenticate() never sets api.requires_2fa, which is what the reauth
        # flow reads to decide whether to ask for a code.
        self.requires_verification_code = two_factor and keep_session
        if start_reauth:
            self._require_reauth()

    def update_devices(self, locate: bool = True) -> None:
        """Update iCloud devices."""
        if self.api is None:
            return
        _LOGGER.debug("Updating devices")

        if self.api.requires_2fa:
            self._require_reauth()
            # Keep the timer running so polling resumes by itself once the
            # user has entered their verification code.
            self._fetch_interval = self._max_interval
            self._schedule_next_fetch()
            return

        try:
            api_devices = self.api.devices
        except Exception as err:
            if _is_auth_failure(err):
                # Refreshing the devices is where a stored session is usually
                # turned down. Retrying that here every couple of minutes gets
                # nowhere, so hand it to the caller, which asks the user.
                raise
            _LOGGER.error("Unknown iCloud error: %s", err)
            self._fetch_interval = 2
            dispatcher_send(self.hass, self.signal_device_update)
            self._schedule_next_fetch()
            return

        if locate:
            # Since pyicloud 2.3.0 device reads are cache-only and the library
            # requests an active locate from Apple only at service creation, so
            # explicitly refresh with locate=True to get a fresh GPS fix on
            # every poll instead of Apple's cached location.
            try:
                api_devices.refresh(locate=True)
            except Exception as err:
                if _is_auth_failure(err):
                    raise
                # Best effort: the devices read below still carry whichever
                # fixes iCloud already held, which beats skipping the poll
                # altogether.
                _LOGGER.debug("Could not request an iCloud location refresh: %s", err)

        if self._owner_fullname is None and api_devices.user_info is not None:
            # setup() returns before reading these when iCloud asks for a
            # verification code, and keep_alive() only runs a full setup again
            # when there is no session at all, so the first poll after the
            # challenge is what fills them in. A family device cannot be built
            # without them.
            self._read_account_names(api_devices.user_info)

        # Gets devices infos
        devices = list(api_devices)
        new_device = False
        first_status: dict[str, Any] | None = None
        for device in devices:
            status = device.status(DEVICE_STATUS_SET)
            device_id = status[DEVICE_ID]
            device_name = status[DEVICE_NAME]

            if device_id is None or device_name is None:
                # status() reports every requested field, using None for the
                # ones iCloud left out, so an unusable device arrives looking
                # like any other rather than raising. It has to be rejected
                # here to keep a None identity out of the entity and device
                # registries; a later poll picks the device up if iCloud
                # starts reporting it properly.
                _LOGGER.warning("Skipping iCloud device with no id or name")
                continue

            # After the skip above, so the pending check below never reads the
            # status of a device that was just rejected.
            if first_status is None:
                first_status = status

            if self._devices.get(device_id) is not None:
                # A device already being tracked is always updated. What
                # follows decides whether to start tracking one, not whether
                # to keep it current: skipping the update would leave the
                # battery and location it has stopped reporting on show.
                _LOGGER.debug("Updating iCloud device: %s", device_name)
                if self._devices[device_id].update(status):
                    new_device = True
                continue

            # Being locatable is what makes a device worth tracking, and
            # iCloud reports no battery for one that is asleep or has none to
            # report. Either on its own is worth keeping: the account feeds
            # the tracker platform and the battery sensors, and each skips
            # what it cannot use. Only a device reporting neither is of no
            # use to either.
            device_location = status.get(DEVICE_LOCATION)
            has_location = _is_usable_location(device_location)
            has_battery = (
                status[DEVICE_BATTERY_STATUS] != "Unknown"
                and status.get(DEVICE_BATTERY_LEVEL) is not None
            )
            if not has_location and not has_battery:
                continue

            _LOGGER.debug(
                "Adding iCloud device: %s [model: %s]",
                device_name,
                status[DEVICE_RAW_DEVICE_MODEL],
            )
            self._devices[device_id] = IcloudDevice(self, device, status)
            self._devices[device_id].update(status)
            new_device = True

        if (
            # status() reports every requested field, using None for the ones
            # iCloud left out; indexing the payload directly would raise here
            # instead, and during setup that is before any timer is armed.
            first_status is not None
            and DEVICE_STATUS_CODES.get(first_status[DEVICE_STATUS]) == "pending"
            and not self._retried_fetch
        ):
            _LOGGER.debug("Pending devices, trying again in 15s")
            self._fetch_interval = 0.25
            self._retried_fetch = True
        else:
            self._fetch_interval = self._determine_interval()
            self._retried_fetch = False

        dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            # Sent once, after the scan: the platforms iterate the account's
            # devices on the event loop, so a signal sent from the middle of
            # the scan could have one iterating while the next device is added.
            dispatcher_send(self.hass, self.signal_device_new)

        self._schedule_next_fetch()

    def _ask_to_authenticate(self, err: Exception) -> None:
        """Ask the user to log in again after iCloud rejected the session.

        The session is only kept when the reauth flow can actually use it.
        That is what api.requires_2fa says: the flow reads exactly that
        property to decide whether to open code entry. A challenge raised by a
        request pyicloud does not route through authenticate() never sets it,
        so keeping that session would send the flow past code entry with a
        code still outstanding; dropping it asks for the password instead, and
        the login that follows re-issues the challenge with requires_2fa set.

        An authentication status on an API response is never that case either:
        it says the session itself has to be established again, and one that
        has just been rejected cannot carry a code.
        """
        if (
            not isinstance(err, PyiCloudAPIResponseException)
            and self.api is not None
            and self.api.requires_2fa
        ):
            # Keep the session: the reauth flow reuses it to validate the code,
            # and async_step_reauth sends a None api back to the password form
            # instead of straight to code entry.
            _LOGGER.warning(
                (
                    "2FA authentication required for '%s'; Go to the Integrations "
                    "menu and click on Configure on the discovered Apple iCloud "
                    "card to enter your verification code"
                ),
                self._config_entry.data[CONF_USERNAME],
            )
        else:
            self.api = None
            _LOGGER.error(
                (
                    "Your iCloud account for '%s' is no longer working; Go to the "
                    "Integrations menu and click on Configure on the discovered "
                    "Apple iCloud card to login again"
                ),
                self._config_entry.data[CONF_USERNAME],
            )
        self._require_reauth()

    def _require_reauth(self):
        """Require the user to log in again."""
        self.hass.add_job(self._config_entry.async_start_reauth, self.hass)

    def _determine_interval(self) -> int:
        """Calculate new interval between two API fetch (in minutes)."""
        intervals = {"default": self._max_interval}
        for device in self._devices.values():
            # Max interval if no location
            if device.location is None:
                continue

            current_zone = run_callback_threadsafe(
                self.hass.loop,
                async_active_zone,
                self.hass,
                device.location[DEVICE_LOCATION_LATITUDE],
                device.location[DEVICE_LOCATION_LONGITUDE],
                device.location[DEVICE_LOCATION_HORIZONTAL_ACCURACY],
            ).result()

            # Max interval if in zone
            if current_zone is not None:
                continue

            zones = (
                self.hass.states.get(entity_id)
                for entity_id in sorted(self.hass.states.entity_ids("zone"))
            )

            distances = []
            for zone_state in zones:
                if zone_state is None:
                    continue
                zone_state_lat = zone_state.attributes[EntityStateAttribute.LATITUDE]
                zone_state_long = zone_state.attributes[EntityStateAttribute.LONGITUDE]
                zone_distance = distance(
                    device.location[DEVICE_LOCATION_LATITUDE],
                    device.location[DEVICE_LOCATION_LONGITUDE],
                    zone_state_lat,
                    zone_state_long,
                )
                if zone_distance is not None:
                    distances.append(round(zone_distance / 1000, 1))

            # Max interval if no zone
            if not distances:
                continue
            mindistance = min(distances)

            # Calculate out how long it would take for the device to drive
            # to the nearest zone at 120 km/h:
            interval = round(mindistance / 2)

            # Never poll more than once per minute
            interval = max(interval, 1)

            if interval > 180:
                # Three hour drive?
                # This is far enough that they might be flying
                interval = self._max_interval

            if (
                device.battery_level is not None
                and device.battery_level <= 33
                and mindistance > 3
            ):
                # Low battery - let's check half as often
                interval = interval * 2

            intervals[device.name] = interval

        return max(
            int(min(intervals.items(), key=operator.itemgetter(1))[1]),
            self._max_interval,
        )

    def cancel_fetch(self) -> None:
        """Cancel the scheduled fetch timer."""
        if self._unsub_fetch is not None:
            self._unsub_fetch()
            self._unsub_fetch = None

    def _schedule_next_fetch(self) -> None:
        self.cancel_fetch()
        if not self._config_entry.pref_disable_polling:
            self._unsub_fetch = track_point_in_utc_time(
                self.hass,
                self.keep_alive,
                utcnow() + timedelta(minutes=self._fetch_interval),
            )

    def _reauth_pending(self) -> bool:
        """Return whether the user is already being asked to log in again.

        This runs in the executor, so the flow list has to be read on the
        event loop like the rest of the shared state here.
        """
        return run_callback_threadsafe(
            self.hass.loop,
            lambda: bool(
                any(
                    self._config_entry.async_get_active_flows(
                        self.hass, {SOURCE_REAUTH}
                    )
                )
            ),
        ).result()

    def keep_alive(self, now=None) -> None:
        """Keep the API alive.

        This runs from a timer callback and is what schedules the next one, so
        every path out of here has to schedule that fetch: anything raised
        escapes into the event loop and stops the account polling entirely.
        """
        if self.api is None and not self._reauth_pending():
            # Not while the user is already being asked: retrying underneath
            # them adds failed attempts against the account, or succeeds and
            # strands the repair they were shown. Completing that flow reloads
            # the entry, which is what recovers the account.
            try:
                self.setup()
            except Exception:
                # setup() reports its own failures; it must not stop the loop.
                # Drop whatever session it did establish: it may have failed
                # after logging in but before reading the account's owner and
                # family names, and those are only filled in by a full setup.
                _LOGGER.exception("Error setting up iCloud account, will retry")
                self.api = None

        if self.api is None:
            # Still no session. Try again at the longest interval rather than
            # giving up, so the account recovers on its own once iCloud is
            # reachable again or the user has finished logging in.
            self._fetch_interval = self._max_interval
            self._schedule_next_fetch()
            return

        try:
            try:
                self.api.authenticate()
                self.update_devices()
            except PyiCloudAPIResponseException as err:
                if not is_auth_error(err):
                    # Not an authentication failure. Hand it to the transient
                    # handling below so it keeps being retried, rather than
                    # parking the account for credentials that are not at fault.
                    raise
                self._ask_to_authenticate(err)
                self._fetch_interval = self._max_interval
                self._schedule_next_fetch()
            except (
                PyiCloud2FARequiredException,
                PyiCloudFailedLoginException,
                PyiCloudAuthRequiredException,
                PyiCloudAcceptTermsException,
            ) as err:
                # None of these comes back on its own, so ask the user instead
                # of retrying every couple of minutes forever.
                self._ask_to_authenticate(err)
                self._fetch_interval = self._max_interval
                self._schedule_next_fetch()
        except Exception:
            # update_devices() reschedules itself on the errors it handles;
            # this covers the rest, such as a device missing fields.
            _LOGGER.exception("Error updating iCloud devices, will retry")
            self._fetch_interval = 2
            self._schedule_next_fetch()

    def get_devices_with_name(self, name: str) -> list[Any]:
        """Get devices by name."""
        name_slug = slugify(name.replace(" ", "", 99))
        result = [
            device
            for device in self.devices.values()
            if slugify(device.name.replace(" ", "", 99)) == name_slug
        ]
        if not result:
            raise ValueError(f"No device with name {name}")
        return result

    @property
    def username(self) -> str:
        """Return the account username."""
        return self._username

    @property
    def owner_fullname(self) -> str | None:
        """Return the account owner fullname."""
        return self._owner_fullname

    @property
    def family_members_fullname(self) -> dict[str, str]:
        """Return the account family members fullname."""
        return self._family_members_fullname

    @property
    def fetch_interval(self) -> float:
        """Return the account fetch interval."""
        return self._fetch_interval

    @property
    def max_interval(self) -> int:
        """Return the longest interval between two fetches, in minutes."""
        return self._max_interval

    @property
    def devices(self) -> dict[str, IcloudDevice]:
        """Return the account devices."""
        return self._devices

    @property
    def signal_device_new(self) -> str:
        """Event specific per Freebox entry to signal new device."""
        return f"{DOMAIN}-{self._username}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Freebox entry to signal updates in devices."""
        return f"{DOMAIN}-{self._username}-device-update"


class IcloudDevice:
    """Representation of a iCloud device."""

    _attr_attribution = "Data provided by Apple iCloud"

    def __init__(self, account: IcloudAccount, device: AppleDevice, status) -> None:
        """Initialize the iCloud device."""
        self._account = account

        self._device = device
        self._status = status

        self._name = self._status[DEVICE_NAME]
        self._device_id = self._status[DEVICE_ID]
        self._device_class = self._status[DEVICE_CLASS]
        self._device_model = self._status[DEVICE_DISPLAY_NAME]

        self._battery_level: int | None = None
        self._battery_status = None
        self._location = None

        self._attrs = {
            ATTR_ACCOUNT_FETCH_INTERVAL: self._account.fetch_interval,
            ATTR_DEVICE_NAME: self._device_model,
            ATTR_DEVICE_STATUS: None,
        }
        if self._status[DEVICE_PERSON_ID]:
            self._attrs[ATTR_OWNER_NAME] = account.family_members_fullname[
                self._status[DEVICE_PERSON_ID]
            ]
        elif account.owner_fullname is not None:
            self._attrs[ATTR_OWNER_NAME] = account.owner_fullname

    def update(self, status) -> bool:
        """Update the iCloud device.

        Returns whether the device has gained something the platforms build
        entities from, so the caller can tell them once its scan is done.
        """
        announce = False
        self._status = status

        self._status[ATTR_ACCOUNT_FETCH_INTERVAL] = self._account.fetch_interval

        device_status = DEVICE_STATUS_CODES.get(self._status[DEVICE_STATUS], "error")
        self._attrs[ATTR_DEVICE_STATUS] = device_status

        self._battery_status = self._status[DEVICE_BATTERY_STATUS]
        self._attrs[ATTR_BATTERY_STATUS] = self._battery_status
        device_battery_level = self._status.get(DEVICE_BATTERY_LEVEL)
        if self._battery_status != "Unknown" and device_battery_level is not None:
            # The battery sensor is created from the new-device signal, and a
            # device kept for its location alone was added without one.
            # Nothing else reports that it has a battery now.
            announce = self._battery_level is None
            self._battery_level = int(device_battery_level * 100)
            self._attrs[ATTR_BATTERY] = self._battery_level
            self._attrs[ATTR_LOW_POWER_MODE] = self._status[DEVICE_LOW_POWER_MODE]
        else:
            # Keeping a device whose battery iCloud has stopped reporting -
            # one that has gone to sleep, say - would otherwise leave the
            # sensor showing the last level it saw for as long as it lasts.
            self._battery_level = None
            self._attrs.pop(ATTR_BATTERY, None)
            self._attrs.pop(ATTR_LOW_POWER_MODE, None)

        # Deliberately not nested under the battery block above: a device
        # iCloud reports no battery for still has a location worth reading.
        location = self._status.get(DEVICE_LOCATION)
        if location and _is_usable_location(location) and not self._is_stale(location):
            announce = announce or self._location is None
            self._location = location
        else:
            # Without a location the tracker reports "unknown" rather than the
            # place the device has since left.
            self._location = None
        return announce

    def _is_stale(self, location: dict[str, Any]) -> bool:
        """Return whether a location fix is too old to be trusted.

        Both signals are needed, because neither is sufficient alone:

        `isOld` says iCloud served a cached fix rather than a fresh one, but
        not why. A device that was briefly unreachable looks exactly like one
        that has genuinely moved away, so acting on the flag by itself would
        drop locations that are still perfectly good.

        The age of the fix alone is no better: a device sitting still keeps
        reporting the same old timestamp while iCloud still considers that fix
        current, and discarding those would throw away the only location such
        a device ever reports.

        Requiring both means a fix is only discarded once iCloud has marked it
        cached *and* it is older than the longest gap between two fetches - by
        which point a fresher one should already have superseded it. The half
        interval of headroom keeps a fix that merely lands late from being
        treated as stale.

        The configured maximum is used rather than the current fetch interval,
        which is recomputed after this runs and drops as low as fifteen
        seconds while devices are still pending - a threshold that short would
        discard every cached fix there is.
        """
        if not location.get(DEVICE_LOCATION_IS_OLD):
            return False

        timestamp = location.get(DEVICE_LOCATION_TIMESTAMP)
        if isinstance(timestamp, bool) or not isinstance(timestamp, int | float):
            # Without a time there is nothing to judge the fix by, and one that
            # is not a number cannot be read as one.
            return False

        try:
            # iCloud reports the fix time in milliseconds.
            fixed_at = datetime.fromtimestamp(timestamp / 1000, tz=UTC)
        except OverflowError, OSError, ValueError:
            # NaN, infinity and values outside the range of a date.
            return False
        age = utcnow() - fixed_at
        return age.total_seconds() > self._account.max_interval * 60 * 1.5

    def play_sound(self) -> None:
        """Play sound on the device."""
        if self._account.api is None:
            return

        self._account.api.authenticate()
        _LOGGER.debug("Playing sound for %s", self.name)
        self.device.play_sound()

    def display_message(self, message: str, sound: bool = False) -> None:
        """Display a message on the device."""
        if self._account.api is None:
            return

        self._account.api.authenticate()
        _LOGGER.debug("Displaying message for %s", self.name)
        self.device.display_message("Subject not working", message, sound)

    def lost_device(self, number: str, message: str) -> None:
        """Make the device in lost state."""
        if self._account.api is None:
            return

        self._account.api.authenticate()
        if self._status[DEVICE_LOST_MODE_CAPABLE]:
            _LOGGER.debug("Make device lost for %s", self.name)
            self.device.lost_device(number, message, None)
        else:
            _LOGGER.error("Cannot make device lost for %s", self.name)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device_id

    @property
    def name(self) -> str:
        """Return the Apple device name."""
        return self._name

    @property
    def device(self) -> AppleDevice:
        """Return the Apple device."""
        return self._device

    @property
    def device_class(self) -> str:
        """Return the Apple device class."""
        return self._device_class

    @property
    def device_model(self) -> str:
        """Return the Apple device model."""
        return self._device_model

    @property
    def battery_level(self) -> int | None:
        """Return the Apple device battery level."""
        return self._battery_level

    @property
    def battery_status(self) -> str | None:
        """Return the Apple device battery status."""
        return self._battery_status

    @property
    def location(self) -> dict[str, Any] | None:
        """Return the Apple device location."""
        return self._location

    @property
    def location_timestamp(self) -> datetime | None:
        """Return when the last location fix was recorded."""
        if self._location is None:
            return None
        return _parse_timestamp(self._location.get(DEVICE_LOCATION_TIMESTAMP))

    @property
    def location_type(self) -> str | None:
        """Return the type of the last location fix, for example GPS or Wifi."""
        if self._location is None:
            return None
        return self._location.get(DEVICE_LOCATION_POSITION_TYPE)

    @property
    def location_accuracy(self) -> float | None:
        """Return the horizontal accuracy of the last location fix in meters."""
        if self._location is None:
            return None
        return self._location.get(DEVICE_LOCATION_HORIZONTAL_ACCURACY)

    @property
    def location_altitude(self) -> float | None:
        """Return the altitude of the last location fix in meters."""
        if self._location is None:
            return None
        return self._location.get(DEVICE_LOCATION_ALTITUDE)

    @property
    def location_floor_level(self) -> int | None:
        """Return the floor level of the last location fix."""
        if self._location is None:
            return None
        return self._location.get(DEVICE_LOCATION_FLOOR_LEVEL)

    @property
    def device_status(self) -> str:
        """Return the device online status."""
        return DEVICE_STATUS_CODES.get(self._status[DEVICE_STATUS], "error")

    @property
    def last_locked(self) -> datetime | None:
        """Return when the device was last locked."""
        return _parse_timestamp(self._status.get(DEVICE_LOCKED_TIMESTAMP))

    @property
    def last_lost(self) -> datetime | None:
        """Return when the device was last put in lost mode."""
        return _parse_timestamp(self._status.get(DEVICE_LOST_TIMESTAMP))

    @property
    def last_wiped(self) -> datetime | None:
        """Return when the device was last wiped."""
        return _parse_timestamp(self._status.get(DEVICE_WIPED_TIMESTAMP))

    @property
    def owner_name(self) -> str | None:
        """Return the full name of the device owner."""
        return self._attrs.get(ATTR_OWNER_NAME)

    @property
    def erase_available(self) -> bool:
        """Return whether the device can be remotely erased."""
        return self._device.erase_available

    @property
    def lock_available(self) -> bool:
        """Return whether the device can be remotely locked."""
        features = self._status.get(DEVICE_FEATURES) or {}
        return bool(features.get(DEVICE_FEATURE_LOCK, False))

    @property
    def location_available(self) -> bool:
        """Return whether the device reports a location."""
        return self._device.location_available

    @property
    def lost_mode_available(self) -> bool:
        """Return whether the device supports lost mode."""
        return self._device.lost_mode_available

    @property
    def sound_available(self) -> bool:
        """Return whether the device can play a sound."""
        return self._device.sound_available

    @property
    def location_is_old(self) -> bool:
        """Return whether Apple flagged the reported location fix as old."""
        # The flag describes the payload Apple just sent, which can differ from
        # the fix this integration stores.
        location = self._status[DEVICE_LOCATION]
        if location is None:
            return False
        return bool(location.get(DEVICE_LOCATION_IS_OLD, False))

    @property
    def location_is_inaccurate(self) -> bool:
        """Return whether Apple flagged the reported location fix as inaccurate."""
        location = self._status[DEVICE_LOCATION]
        if location is None:
            return False
        return bool(location.get(DEVICE_LOCATION_IS_INACCURATE, False))

    @property
    def is_online(self) -> bool:
        """Return whether the device is online."""
        return self.device_status == "online"

    @property
    def low_power_mode(self) -> bool:
        """Return whether low power mode is enabled on the device."""
        return bool(self._status.get(DEVICE_LOW_POWER_MODE, False))

    @property
    def activation_locked(self) -> bool:
        """Return whether activation lock is enabled on the device."""
        return bool(self._status.get(DEVICE_ACTIVATION_LOCKED, False))

    @property
    def is_locating(self) -> bool:
        """Return whether the device is being located right now."""
        return bool(self._status.get(DEVICE_IS_LOCATING, False))

    @property
    def location_services_enabled(self) -> bool:
        """Return whether location services are enabled on the device."""
        return bool(self._status.get(DEVICE_LOCATION_ENABLED, False))

    @property
    def wipe_in_progress(self) -> bool:
        """Return whether a wipe is in progress on the device."""
        return bool(self._status.get(DEVICE_WIPE_IN_PROGRESS, False))

    @property
    def remote_lock_pending(self) -> bool:
        """Return whether a remote lock is pending on the device."""
        remote_lock = self._status.get(DEVICE_REMOTE_LOCK)
        if not isinstance(remote_lock, dict):
            return False
        return (
            remote_lock.get(DEVICE_ACTION_STATUS_CODE) == DEVICE_ACTION_STATUS_PENDING
        )

    @property
    def lost_mode_enabled(self) -> bool:
        """Return whether lost mode is currently enabled on the device."""
        return bool(self._status.get(DEVICE_LOST_MODE_ENABLED, False))

    @property
    def raw_status(self) -> dict[str, Any]:
        """Return the raw device data reported by Apple."""
        # update() stores the fetch interval in the status dict, which is
        # account state rather than device data.
        return {
            key: value
            for key, value in self._status.items()
            if key != ATTR_ACCOUNT_FETCH_INTERVAL
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return self._attrs
