"""iCloud account."""
from datetime import timedelta
import logging
import operator
from typing import Dict

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException, PyiCloudNoDevicesException
from pyicloud.services.findmyiphone import AppleDevice

from homeassistant.components.zone import async_active_zone
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.dt import utcnow
from homeassistant.util.location import distance

from .const import (
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
    SERVICE_UPDATE,
)

ATTRIBUTION = "Data provided by Apple iCloud"

# entity attributes
ATTR_ACCOUNT_FETCH_INTERVAL = "account_fetch_interval"
ATTR_BATTERY = "battery"
ATTR_BATTERY_STATUS = "battery_status"
ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_STATUS = "device_status"
ATTR_LOW_POWER_MODE = "low_power_mode"
ATTR_OWNER_NAME = "owner_fullname"

# services
SERVICE_ICLOUD_PLAY_SOUND = "play_sound"
SERVICE_ICLOUD_DISPLAY_MESSAGE = "display_message"
SERVICE_ICLOUD_LOST_DEVICE = "lost_device"
SERVICE_ICLOUD_UPDATE = "update"
ATTR_ACCOUNT = "account"
ATTR_LOST_DEVICE_MESSAGE = "message"
ATTR_LOST_DEVICE_NUMBER = "number"
ATTR_LOST_DEVICE_SOUND = "sound"

_LOGGER = logging.getLogger(__name__)


class IcloudAccount:
    """Representation of an iCloud account."""

    def __init__(
        self,
        hass: HomeAssistantType,
        username: str,
        password: str,
        icloud_dir: Store,
        max_interval: int,
        gps_accuracy_threshold: int,
    ):
        """Initialize an iCloud account."""
        self.hass = hass
        self._username = username
        self._password = password
        self._fetch_interval = max_interval
        self._max_interval = max_interval
        self._gps_accuracy_threshold = gps_accuracy_threshold

        self._icloud_dir = icloud_dir

        self.api: PyiCloudService = None
        self._owner_fullname = None
        self._family_members_fullname = {}
        self._devices = {}

        self.unsub_device_tracker = None

    def setup(self) -> None:
        """Set up an iCloud account."""
        try:
            self.api = PyiCloudService(
                self._username, self._password, self._icloud_dir.path
            )
        except PyiCloudFailedLoginException as error:
            self.api = None
            _LOGGER.error("Error logging into iCloud Service: %s", error)
            return

        user_info = None
        try:
            # Gets device owners infos
            user_info = self.api.devices.response["userInfo"]
        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud device found")
            return

        self._owner_fullname = f"{user_info['firstName']} {user_info['lastName']}"

        self._family_members_fullname = {}
        if user_info.get("membersInfo") is not None:
            for prs_id, member in user_info["membersInfo"].items():
                self._family_members_fullname[
                    prs_id
                ] = f"{member['firstName']} {member['lastName']}"

        self._devices = {}
        self.update_devices()

    def update_devices(self) -> None:
        """Update iCloud devices."""
        if self.api is None:
            return

        api_devices = {}
        try:
            api_devices = self.api.devices
        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud device found")
            return
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unknown iCloud error: %s", err)
            self._fetch_interval = 5
            dispatcher_send(self.hass, SERVICE_UPDATE)
            track_point_in_utc_time(
                self.hass,
                self.keep_alive,
                utcnow() + timedelta(minutes=self._fetch_interval),
            )
            return

        # Gets devices infos
        for device in api_devices:
            status = device.status(DEVICE_STATUS_SET)
            device_id = status[DEVICE_ID]
            device_name = status[DEVICE_NAME]

            if self._devices.get(device_id, None) is not None:
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

        self._fetch_interval = self._determine_interval()
        dispatcher_send(self.hass, SERVICE_UPDATE)
        track_point_in_utc_time(
            self.hass,
            self.keep_alive,
            utcnow() + timedelta(minutes=self._fetch_interval),
        )

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
                zone_state_lat = zone_state.attributes[DEVICE_LOCATION_LATITUDE]
                zone_state_long = zone_state.attributes[DEVICE_LOCATION_LONGITUDE]
                zone_distance = distance(
                    device.location[DEVICE_LOCATION_LATITUDE],
                    device.location[DEVICE_LOCATION_LONGITUDE],
                    zone_state_lat,
                    zone_state_long,
                )
                distances.append(round(zone_distance / 1000, 1))

            # Max interval if no zone
            if not distances:
                continue
            mindistance = min(distances)

            # Calculate out how long it would take for the device to drive
            # to the nearest zone at 120 km/h:
            interval = round(mindistance / 2, 0)

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

    def keep_alive(self, now=None) -> None:
        """Keep the API alive."""
        if self.api is None:
            self.setup()

        if self.api is None:
            return

        self.api.authenticate()
        self.update_devices()

    def get_devices_with_name(self, name: str) -> [any]:
        """Get devices by name."""
        result = []
        name_slug = slugify(name.replace(" ", "", 99))
        for device in self.devices.values():
            if slugify(device.name.replace(" ", "", 99)) == name_slug:
                result.append(device)
        if not result:
            raise Exception(f"No device with name {name}")
        return result

    @property
    def username(self) -> str:
        """Return the account username."""
        return self._username

    @property
    def owner_fullname(self) -> str:
        """Return the account owner fullname."""
        return self._owner_fullname

    @property
    def family_members_fullname(self) -> Dict[str, str]:
        """Return the account family members fullname."""
        return self._family_members_fullname

    @property
    def fetch_interval(self) -> int:
        """Return the account fetch interval."""
        return self._fetch_interval

    @property
    def devices(self) -> Dict[str, any]:
        """Return the account devices."""
        return self._devices


class IcloudDevice:
    """Representation of a iCloud device."""

    def __init__(self, account: IcloudAccount, device: AppleDevice, status):
        """Initialize the iCloud device."""
        self._account = account

        self._device = device
        self._status = status

        self._name = self._status[DEVICE_NAME]
        self._device_id = self._status[DEVICE_ID]
        self._device_class = self._status[DEVICE_CLASS]
        self._device_model = self._status[DEVICE_DISPLAY_NAME]

        if self._status[DEVICE_PERSON_ID]:
            owner_fullname = account.family_members_fullname[
                self._status[DEVICE_PERSON_ID]
            ]
        else:
            owner_fullname = account.owner_fullname

        self._battery_level = None
        self._battery_status = None
        self._location = None

        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_ACCOUNT_FETCH_INTERVAL: self._account.fetch_interval,
            ATTR_DEVICE_NAME: self._device_model,
            ATTR_DEVICE_STATUS: None,
            ATTR_OWNER_NAME: owner_fullname,
        }

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
    def battery_level(self) -> int:
        """Return the Apple device battery level."""
        return self._battery_level

    @property
    def battery_status(self) -> str:
        """Return the Apple device battery status."""
        return self._battery_status

    @property
    def location(self) -> Dict[str, any]:
        """Return the Apple device location."""
        return self._location

    @property
    def state_attributes(self) -> Dict[str, any]:
        """Return the attributes."""
        return self._attrs
