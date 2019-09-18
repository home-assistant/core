"""The iCloud component."""
from datetime import timedelta
import logging
import operator
from typing import Dict

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException, PyiCloudNoDevicesException
from pyicloud.services.findmyiphone import AppleDevice
import voluptuous as vol

from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import slugify
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.dt import utcnow
from homeassistant.util.location import distance

from .const import (
    CONF_ACCOUNT_NAME,
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_MAX_INTERVAL,
    DOMAIN,
    ICLOUD_COMPONENTS,
    TRACKER_UPDATE,
    DEVICE_BATTERY_LEVEL,
    DEVICE_BATTERY_STATUS,
    DEVICE_CLASS,
    DEVICE_DISPLAY_NAME,
    DEVICE_LOCATION,
    DEVICE_LOCATION_LATITUDE,
    DEVICE_LOCATION_LONGITUDE,
    DEVICE_LOST_MODE_CAPABLE,
    DEVICE_LOW_POWER_MODE,
    DEVICE_NAME,
    DEVICE_PERSON_ID,
    DEVICE_STATUS,
    DEVICE_STATUS_SET,
    DEVICE_STATUS_CODES,
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

_LOGGER = logging.getLogger(__name__)

SERVICE_ICLOUD_PLAY_SOUND = "play_sound"
SERVICE_ICLOUD_DISPLAY_MESSAGE = "display_message"
SERVICE_ICLOUD_LOST_DEVICE = "lost_device"
SERVICE_ICLOUD_UPDATE = "update"
SERVICE_ICLOUD_RESET = "reset"
SERVICE_ATTR_USERNAME = CONF_USERNAME
SERVICE_ATTR_LOST_DEVICE_MESSAGE = "message"
SERVICE_ATTR_LOST_DEVICE_NUMBER = "number"
SERVICE_ATTR_LOST_DEVICE_SOUND = "sound"

SERVICE_SCHEMA = vol.Schema({vol.Optional(SERVICE_ATTR_USERNAME): cv.string})

SERVICE_SCHEMA_PLAY_SOUND = vol.Schema(
    {
        vol.Required(SERVICE_ATTR_USERNAME): cv.string,
        vol.Required(ATTR_DEVICE_NAME): cv.string,
    }
)

SERVICE_SCHEMA_DISPLAY_MESSAGE = vol.Schema(
    {
        vol.Required(SERVICE_ATTR_USERNAME): cv.string,
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(SERVICE_ATTR_LOST_DEVICE_MESSAGE): cv.string,
        vol.Optional(SERVICE_ATTR_LOST_DEVICE_SOUND): cv.boolean,
    }
)

SERVICE_SCHEMA_LOST_DEVICE = vol.Schema(
    {
        vol.Required(SERVICE_ATTR_USERNAME): cv.string,
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(SERVICE_ATTR_LOST_DEVICE_NUMBER): cv.string,
        vol.Required(SERVICE_ATTR_LOST_DEVICE_MESSAGE): cv.string,
    }
)

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_ACCOUNT_NAME): cv.slugify,
        vol.Optional(CONF_MAX_INTERVAL, default=DEFAULT_MAX_INTERVAL): cv.positive_int,
        vol.Optional(
            CONF_GPS_ACCURACY_THRESHOLD, default=DEFAULT_GPS_ACCURACY_THRESHOLD
        ): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [ACCOUNT_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up iCloud from legacy config file."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for account_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=account_conf.copy()
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up an iCloud account from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    account_name = entry.data.get(CONF_ACCOUNT_NAME)
    max_interval = entry.data[CONF_MAX_INTERVAL]
    gps_accuracy_threshold = entry.data[CONF_GPS_ACCURACY_THRESHOLD]

    account = IcloudAccount(
        hass, username, password, account_name, max_interval, gps_accuracy_threshold
    )
    await hass.async_add_executor_job(account.reset_account)
    hass.data[DOMAIN][username] = account

    for component in ICLOUD_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    def play_sound(service):
        """Play sound on the device."""
        username = entry.data[SERVICE_ATTR_USERNAME]
        devicename = service.data.get(ATTR_DEVICE_NAME)
        devicename = slugify(devicename.replace(" ", "", 99))

        hass.data[DOMAIN][username].devices[devicename].play_sound()

    def display_message(service):
        """Display a message on the device."""
        username = entry.data[SERVICE_ATTR_USERNAME]
        devicename = service.data.get(ATTR_DEVICE_NAME)
        devicename = slugify(devicename.replace(" ", "", 99))
        message = service.data.get(SERVICE_ATTR_LOST_DEVICE_MESSAGE)
        sound = service.data.get(SERVICE_ATTR_LOST_DEVICE_SOUND, False)

        hass.data[DOMAIN][username].devices[devicename].display_message(message, sound)

    def lost_device(service):
        """Make the device in lost state."""
        username = entry.data[SERVICE_ATTR_USERNAME]
        devicename = service.data.get(ATTR_DEVICE_NAME)
        devicename = slugify(devicename.replace(" ", "", 99))
        number = service.data.get(SERVICE_ATTR_LOST_DEVICE_NUMBER)
        message = service.data.get(SERVICE_ATTR_LOST_DEVICE_MESSAGE)

        hass.data[DOMAIN][username].devices[devicename].lost_device(number, message)

    def update_account(service):
        """Call the update function of an iCloud account."""
        username = entry.data.get(SERVICE_ATTR_USERNAME)

        if username is None:
            for account in hass.data[DOMAIN].items():
                account.keep_alive(utcnow())
        else:
            hass.data[DOMAIN][username].keep_alive(utcnow())

    def reset_account(service):
        """Reset an iCloud account."""
        username = entry.data.get(SERVICE_ATTR_USERNAME)

        if username is None:
            for account in hass.data[DOMAIN].items():
                account.reset_account()
        else:
            hass.data[DOMAIN][username].reset_account()

    hass.services.async_register(
        DOMAIN, SERVICE_ICLOUD_PLAY_SOUND, play_sound, schema=SERVICE_SCHEMA_PLAY_SOUND
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ICLOUD_DISPLAY_MESSAGE,
        display_message,
        schema=SERVICE_SCHEMA_DISPLAY_MESSAGE,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ICLOUD_LOST_DEVICE,
        lost_device,
        schema=SERVICE_SCHEMA_LOST_DEVICE,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ICLOUD_UPDATE, update_account, schema=SERVICE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ICLOUD_RESET, reset_account, schema=SERVICE_SCHEMA
    )

    return True


class IcloudAccount:
    """Representation of an iCloud account."""

    def __init__(
        self,
        hass,
        username: str,
        password: str,
        accountname: str,
        max_interval: int,
        gps_accuracy_threshold: int,
    ):
        """Initialize an iCloud account."""
        self.hass = hass
        self._username = username
        self._password = password
        self._name = accountname or slugify(username.partition("@")[0])
        self._fetch_interval = max_interval
        self._max_interval = max_interval
        self._gps_accuracy_threshold = gps_accuracy_threshold

        self.api = None
        self._owner_fullname = None
        self._family_members_fullname = {}
        self._devices = {}

        self.unsub_device_tracker = None

    def reset_account(self):
        """Reset an iCloud account."""
        icloud_dir = self.hass.config.path("icloud")

        try:
            self.api = PyiCloudService(self._username, self._password, icloud_dir)
        except PyiCloudFailedLoginException as error:
            self.api = None
            _LOGGER.error("Error logging into iCloud Service: %s", error)
            return

        user_info = None
        try:
            # Gets device owners infos
            user_info = self.api.devices.response["userInfo"]
        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud Devices found")

        self._owner_fullname = f"{user_info['firstName']} {user_info['lastName']}"

        self._family_members_fullname = {}
        for prs_id, member in user_info["membersInfo"].items():
            self._family_members_fullname[
                prs_id
            ] = f"{member['firstName']} {member['lastName']}"

        self._devices = {}
        self.update_devices()

    def update_devices(self):
        """Update iCloud devices."""
        if self.api is None:
            return

        api_devices = {}
        try:
            api_devices = self.api.devices
        except PyiCloudNoDevicesException:
            _LOGGER.error("No iCloud Devices found")

        # Gets devices infos
        for device in api_devices:
            status = device.status(DEVICE_STATUS_SET)
            devicename = slugify(status[DEVICE_NAME].replace(" ", "", 99))

            if self._devices.get(devicename, None) is not None:
                # Seen device -> updating
                _LOGGER.debug("Updating iCloud device: %s", devicename)
                self._devices[devicename].update(status)
            else:
                # New device, should be unique
                if devicename in self._devices:
                    _LOGGER.error("Multiple devices with name: %s", devicename)
                    continue

                _LOGGER.debug("Adding iCloud device: %s", devicename)
                self._devices[devicename] = IcloudDevice(self, device, status)
                self._devices[devicename].update(status)

        dispatcher_send(self.hass, TRACKER_UPDATE)
        self._fetch_interval = self.determine_interval()
        track_point_in_utc_time(
            self.hass,
            self.keep_alive,
            utcnow() + timedelta(minutes=self._fetch_interval),
        )

    def determine_interval(self) -> int:
        """Calculate new interval between two API fetch (in minutes)."""
        intervals = {}
        for device in self._devices.values():
            if device.location is None:
                continue

            current_zone = run_callback_threadsafe(
                self.hass.loop,
                async_active_zone,
                self.hass,
                device.location[DEVICE_LOCATION_LATITUDE],
                device.location[DEVICE_LOCATION_LONGITUDE],
            ).result()

            if current_zone is not None:
                intervals[device.name] = self._max_interval
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

    def keep_alive(self, now):
        """Keep the API alive."""
        if self.api is None:
            self.reset_account()

        if self.api is None:
            return

        self.api.authenticate()
        self.update_devices()

    @property
    def name(self) -> str:
        """Return the account name."""
        return self._name

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
        self.hass = account.hass
        self._account = account
        account_name = account.name
        account_name_slug = slugify(account_name.partition("@")[0])

        self._device = device
        self._status = status

        self._name = self._status[DEVICE_NAME]
        self._dev_id = slugify(self._name.replace(" ", "", 99))  # devicename
        self._unique_id = f"{account_name_slug}_{self._dev_id}"
        self._device_class = self._status[DEVICE_CLASS]
        device_name = self._status[DEVICE_DISPLAY_NAME]

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
            CONF_ACCOUNT_NAME: account_name,
            ATTR_ACCOUNT_FETCH_INTERVAL: self._account.fetch_interval,
            ATTR_DEVICE_NAME: device_name,
            ATTR_DEVICE_STATUS: None,
            ATTR_OWNER_NAME: owner_fullname,
        }

    def update(self, status):
        """Update the iCloud device."""
        self._status = status

        self._status[ATTR_ACCOUNT_FETCH_INTERVAL] = self._account.fetch_interval

        device_status = DEVICE_STATUS_CODES.get(self._status[DEVICE_STATUS], "error")
        self._attrs[ATTR_DEVICE_STATUS] = device_status

        if self._status[DEVICE_BATTERY_STATUS] != "Unknown":
            self._battery_level = int(self._status.get(DEVICE_BATTERY_LEVEL, 0) * 100)
            self._battery_status = self._status[DEVICE_BATTERY_STATUS]
            low_power_mode = self._status[DEVICE_LOW_POWER_MODE]

            self._attrs[ATTR_BATTERY] = self._battery_level
            self._attrs[ATTR_BATTERY_STATUS] = self._battery_status
            self._attrs[ATTR_LOW_POWER_MODE] = low_power_mode

            if (
                self._status[DEVICE_LOCATION]
                and self._status[DEVICE_LOCATION][DEVICE_LOCATION_LATITUDE]
            ):
                location = self._status[DEVICE_LOCATION]
                self._location = location

    def play_sound(self):
        """Play sound on the device."""
        if self._account.api is None:
            return

        self._account.api.authenticate()
        _LOGGER.debug("Playing sound for %s", self.name)
        self.device.play_sound()

    def display_message(self, message: str, sound: bool = False):
        """Display a message on the device."""
        if self._account.api is None:
            return

        self._account.api.authenticate()
        _LOGGER.debug("Displaying message for %s", self.name)
        self.device.display_message("Subject not working", message, sound)

    def lost_device(self, number: str, message: str):
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
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the Apple device name."""
        return self._name

    @property
    def device(self) -> AppleDevice:
        """Return the Apple device."""
        return self._device

    @property
    def dev_id(self) -> str:
        """Return the device ID."""
        return self._dev_id

    @property
    def device_class(self) -> str:
        """Return the Apple device class."""
        return self._device_class

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
