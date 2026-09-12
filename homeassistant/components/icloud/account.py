"""iCloud account."""

from datetime import timedelta
import logging
import operator
from typing import TYPE_CHECKING, Any

from pyicloud import PyiCloudService
from pyicloud.const import AppleAuthError
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloudAPIResponseException,
    PyiCloudAuthRequiredException,
    PyiCloudFailedLoginException,
    PyiCloudNoDevicesException,
    PyiCloudServiceNotActivatedException,
    PyiCloudServiceUnavailable,
)
from pyicloud.services.findmyiphone import AppleDevice

from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, EntityStateAttribute
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.dt import utcnow
from homeassistant.util.location import distance

from .const import (
    ATTR_ACCOUNT_FETCH_INTERVAL,
    ATTR_BATTERY,
    ATTR_BATTERY_STATUS,
    ATTR_DEVICE_NAME,
    ATTR_DEVICE_STATUS,
    ATTR_LOW_POWER_MODE,
    ATTR_OWNER_NAME,
    DEVICE_BATTERY_LEVEL,
    DEVICE_BATTERY_STATUS,
    DEVICE_CLASS,
    DEVICE_DISPLAY_NAME,
    DEVICE_ID,
    DEVICE_LOCATION,
    DEVICE_LOCATION_HORIZONTAL_ACCURACY,
    DEVICE_LOCATION_LATITUDE,
    DEVICE_LOCATION_LONGITUDE,
    DEVICE_LOST_MODE_CAPABLE,
    DEVICE_LOW_POWER_MODE,
    DEVICE_NAME,
    DEVICE_PERSON_ID,
    DEVICE_RAW_DEVICE_MODEL,
    DEVICE_STATUS,
    DEVICE_STATUS_CODES,
    DEVICE_STATUS_SET,
    DOMAIN,
)

if TYPE_CHECKING:
    from .coordinator import IcloudCalendarCoordinator, IcloudRemindersCoordinator
    from .media_source import PhotoCache

_LOGGER = logging.getLogger(__name__)

# Most authentication rejections arrive as a plain PyiCloudAPIResponseException
# carrying the HTTP status in .code, so the status is what has to be inspected
# rather than the exception type.
#
# GENERAL_AUTH_ERROR (500) is left out on purpose: pyicloud groups it with the
# authentication statuses, but a 500 is just as likely to be a transient iCloud
# failure, and asking the user to log in again for those would be wrong.
_AUTH_REQUIRED_STATUSES = frozenset(
    {
        AppleAuthError.TWO_FACTOR_REQUIRED,
        AppleAuthError.LOGIN_TOKEN_EXPIRED,
        AppleAuthError.FIND_MY_REAUTH_REQUIRED,
    }
)


def _is_auth_error(err: PyiCloudAPIResponseException) -> bool:
    """Return True if the account has to authenticate again to recover."""
    return isinstance(err.code, int) and err.code in _AUTH_REQUIRED_STATUSES


type IcloudConfigEntry = ConfigEntry[IcloudAccount]


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
        """Set up an iCloud account."""
        try:
            self.api = PyiCloudService(
                self._username,
                self._password,
                self._icloud_dir.path,
                with_family=self._with_family,
            )

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
            if not _is_auth_error(err):
                raise
            self._handle_auth_required(two_factor=False, keep_session=False)
            return

        if self.api.requires_2fa:
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
            self._handle_auth_required(two_factor=True, keep_session=True)
            raise ConfigEntryNotReady from err
        except (PyiCloudFailedLoginException, PyiCloudAuthRequiredException) as err:
            # Reading the devices refreshes the session, and a stored token
            # that iCloud has since invalidated is only rejected here, not
            # while logging in. Ask for reauth so the user has something to
            # act on, and still raise: the fetch timer is only armed at the
            # end of update_devices(), so returning here would leave an entry
            # that is loaded and never polls again.
            challenged = self.api is not None and self.api.requires_2fa
            self._handle_auth_required(two_factor=challenged, keep_session=challenged)
            raise ConfigEntryNotReady from err
        except (
            PyiCloudServiceNotActivatedException,
            PyiCloudNoDevicesException,
            PyiCloudServiceUnavailable,
        ) as err:
            _LOGGER.error("No iCloud device found")
            raise ConfigEntryNotReady from err
        except PyiCloudAPIResponseException as err:
            # Has to stay below the clause above: PyiCloudServiceNotActivatedException
            # is a subclass of this one and would otherwise never be reached.
            if not _is_auth_error(err):
                raise
            # Drop the session instead of keeping it for a code: it has just
            # failed to refresh, so a reauth flow sending a code through it
            # would fail as well.
            self._handle_auth_required(two_factor=False, keep_session=False)
            raise ConfigEntryNotReady from err

        if user_info is None:
            raise ConfigEntryNotReady("No user info found in iCloud devices response")

        self._owner_fullname = (
            f"{user_info.get('firstName')} {user_info.get('lastName')}"
        )

        self._family_members_fullname = {}
        if user_info.get("membersInfo") is not None:
            for prs_id, member in user_info.get("membersInfo").items():
                self._family_members_fullname[prs_id] = (
                    f"{member['firstName']} {member['lastName']}"
                )

        self._devices = {}
        self.update_devices()

    def _handle_auth_required(self, *, two_factor: bool, keep_session: bool) -> None:
        """Report why authentication failed and start the reauth flow.

        two_factor says what iCloud asked for, keep_session whether there is a
        session to ask through: a 2FA challenge raised before the session was
        established leaves nothing to send a code over, so the user has to log
        in again even though a code is what iCloud wants.
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
        self._require_reauth()

    def update_devices(self) -> None:
        """Update iCloud devices."""
        if self.api is None:
            return
        _LOGGER.debug("Updating devices")

        if self.api.requires_2fa:
            self._require_reauth()
            return

        api_devices = {}
        try:
            api_devices = self.api.devices
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Unknown iCloud error: %s", err)
            self._fetch_interval = 2
            dispatcher_send(self.hass, self.signal_device_update)
            self._schedule_next_fetch()
            return

        # Gets devices infos
        new_device = False
        for device in api_devices:
            status = device.status(DEVICE_STATUS_SET)
            device_id = status[DEVICE_ID]
            device_name = status[DEVICE_NAME]

            if (
                status[DEVICE_BATTERY_STATUS] == "Unknown"
                or status.get(DEVICE_BATTERY_LEVEL) is None
            ):
                continue

            if self._devices.get(device_id) is not None:
                # Seen device -> updating
                _LOGGER.debug("Updating iCloud device: %s", device_name)
                self._devices[device_id].update(status)
            else:
                # New device, should be unique
                _LOGGER.debug(
                    "Adding iCloud device: %s [model: %s]",
                    device_name,
                    status[DEVICE_RAW_DEVICE_MODEL],
                )
                self._devices[device_id] = IcloudDevice(self, device, status)
                self._devices[device_id].update(status)
                new_device = True

        if (
            DEVICE_STATUS_CODES.get(list(api_devices)[0][DEVICE_STATUS]) == "pending"
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
            dispatcher_send(self.hass, self.signal_device_new)

        self._schedule_next_fetch()

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

    def keep_alive(self, now=None) -> None:
        """Keep the API alive."""
        if self.api is None:
            self.setup()

        if self.api is None:
            return

        self.api.authenticate()
        self.update_devices()

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
    def devices(self) -> dict[str, Any]:
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

    def update(self, status) -> None:
        """Update the iCloud device."""
        self._status = status

        self._status[ATTR_ACCOUNT_FETCH_INTERVAL] = self._account.fetch_interval

        device_status = DEVICE_STATUS_CODES.get(self._status[DEVICE_STATUS], "error")
        self._attrs[ATTR_DEVICE_STATUS] = device_status

        self._battery_status = self._status[DEVICE_BATTERY_STATUS]
        self._attrs[ATTR_BATTERY_STATUS] = self._battery_status
        device_battery_level = self._status.get(DEVICE_BATTERY_LEVEL, 0)
        if self._battery_status != "Unknown" and device_battery_level is not None:
            self._battery_level = int(device_battery_level * 100)
            self._attrs[ATTR_BATTERY] = self._battery_level
            self._attrs[ATTR_LOW_POWER_MODE] = self._status[DEVICE_LOW_POWER_MODE]

            if (
                self._status[DEVICE_LOCATION]
                and self._status[DEVICE_LOCATION][DEVICE_LOCATION_LATITUDE]
            ):
                location = self._status[DEVICE_LOCATION]
                if self._location is None:
                    dispatcher_send(self._account.hass, self._account.signal_device_new)
                self._location = location

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return self._attrs
