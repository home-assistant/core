"""Common code for decora_wifi."""

from __future__ import annotations

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity

from .const import LIGHT_DOMAIN, PLATFORMS


class DecoraWifiError(HomeAssistantError):
    """Base for errors raised when the decora_wifi integration encounters an issue."""


class CommFailed(DecoraWifiError):
    """Raised when DecoraWifiPlatform.login() fails to communicate with the myLeviton Service."""


class SessionEntityNotFound(DecoraWifiError):
    """Raised if a platform fails to find the session entity during setup."""


class LoginFailed(DecoraWifiError):
    """Raised when DecoraWifiPlatform.login() fails to log in."""


class LoginMismatch(DecoraWifiError):
    """Raised if the userid returned on reauth does not match the userid cached when the integration was originally set up."""


class DecoraWifiPlatform(BinarySensorEntity):
    """Class to hold decora_wifi platform sessions and related methods."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(self, email: str, password: str) -> None:
        """Iniialize session holder."""
        self._session = DecoraWiFiSession()
        self._email = email
        self._name = f"Decora_Wifi - {self._email}"
        self._password = password
        self._iot_switches: dict[str, IotSwitch] = {
            platform: [] for platform in PLATFORMS
        }
        self._user_id = None
        self._loggedin = False

    @property
    def active_platforms(self) -> list[str]:
        """Get the list of platforms which have devices defined."""
        return [p for p in PLATFORMS if self._iot_switches[p]]

    @property
    def is_on(self) -> bool | None:
        """Return BinarySensorEntity State."""
        return self._loggedin

    @property
    def lights(self) -> list[IotSwitch]:
        """Get the lights."""
        return self._iot_switches[LIGHT_DOMAIN]

    @property
    def name(self) -> str | None:
        """Return Entity Friendly Name."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Get whether entity should be polled."""
        return False

    @property
    def unique_id(self) -> str | None:
        """Return Entity unique_id."""
        return self._user_id

    def _api_login(self):
        """Log in to decora_wifi session."""
        try:
            user = self._session.login(self._email, self._password)

            # If the call to the decora_wifi API's session.login returns None, there was a problem with the credentials.
            if user is None:
                self._loggedin = False
                raise LoginFailed
        except ValueError as exc:
            self._loggedin = False
            raise CommFailed from exc
        self._loggedin = True
        if self.platform:
            self.schedule_update_ha_state()
        self._user_id = user._id

    def _api_logout(self):
        """Log out of decora_wifi session."""
        if self._loggedin:
            try:
                Person.logout(self._session)
            except ValueError as exc:
                raise CommFailed from exc
        self._loggedin = False
        if self.platform:
            self.schedule_update_ha_state()

    def _api_get_devices(self):
        """Update the device library from the API."""

        try:
            # Gather all the available devices into the iot_switches dictionary...
            perms = self._session.user.get_residential_permissions()

            for permission in perms:
                if permission.residentialAccountId is not None:
                    acct = ResidentialAccount(
                        self._session, permission.residentialAccountId
                    )
                    residences = acct.get_residences()
                    for res in residences:
                        switches = res.get_iot_switches()
                        for switch in switches:
                            # Add the switch to the appropriate list in the iot_switches dictionary.
                            platform = DecoraWifiPlatform.classifydevice(switch)
                            self._iot_switches[platform].append(switch)
                elif permission.residenceId is not None:
                    residence = Residence(self._session, permission.residenceId)
                    switches = residence.get_iot_switches()
                    for switch in switches:
                        # Add the switch to the appropriate list in the iot_switches dictionary.
                        platform = DecoraWifiPlatform.classifydevice(switch)
                        self._iot_switches[platform].append(switch)
        except ValueError as exc:
            self._loggedin = False
            if self.platform:
                self.schedule_update_ha_state()
            raise CommFailed from exc

    def reauth(self):
        """Reauthenticate this object's session."""
        self._api_logout()
        self._session = DecoraWiFiSession()
        self._api_login()

    def refresh_devices(self):
        """Refresh this object's devices."""
        self._iot_switches: dict[str, IotSwitch] = {
            platform: [] for platform in PLATFORMS
        }
        self._api_get_devices()

    def setup(self):
        """Set up the session after object instantiation."""
        self._api_login()
        self._api_get_devices()

    def teardown(self):
        """Clean up the session on object deletion."""
        self._api_logout()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self.teardown()

    @staticmethod
    async def async_setup_decora_wifi(hass: HomeAssistant, email: str, password: str):
        """Set up a decora wifi session."""

        def setupplatform() -> DecoraWifiPlatform:
            platform = DecoraWifiPlatform(email, password)
            platform.setup()
            return platform

        return await hass.async_add_executor_job(setupplatform)

    @staticmethod
    def classifydevice(dev):
        """Classify devices by platform."""
        # The light platform is the only one currently implemented in the integration.
        return LIGHT_DOMAIN


class DecoraWifiEntity(Entity):
    """Initiate Decora Wifi Base Class."""

    def __init__(self, device: IotSwitch):
        """Initialize Decora Wifi device base class."""
        self._switch = device
        self._unique_id = device.mac

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._switch.name

    @property
    def unique_id(self):
        """Return the unique id of the switch."""
        return self._unique_id
