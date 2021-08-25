"""Common code for decora_wifi."""

from __future__ import annotations

import logging

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LIGHT_DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class DecoraWifiLoginFailed(Exception):
    """Raised when DecoraWifiPlatform.login() fails to log in."""


class DecoraWifiCommFailed(Exception):
    """Raised when DecoraWifiPlatform.login() fails to communicate with the myLeviton Service."""


class DecoraWifiPlatform:
    """Class to hold decora_wifi platform sessions and related methods."""

    def __init__(self, email: str, password: str) -> None:
        """Iniialize session holder."""
        self._session = DecoraWiFiSession()
        self._email = email
        self._password = password
        self._iot_switches: dict[str, IotSwitch] = {
            platform: [] for platform in PLATFORMS
        }
        self._loggedin = False

    def setup(self):
        """Set up the session after object instantiation."""
        self._api_login()
        self._api_get_devices()

    def teardown(self):
        """Clean up the session on object deletion."""
        self.api_logout()

    @property
    def lights(self) -> list[IotSwitch]:
        """Get the lights."""
        return self._iot_switches[LIGHT_DOMAIN]

    @property
    def active_platforms(self) -> list[str]:
        """Get the list of platforms which have devices defined."""
        return [p for p in PLATFORMS if self._iot_switches[p]]

    def _api_login(self):
        """Log in to decora_wifi session."""
        try:
            success = self._session.login(self._email, self._password)

            # If the call to the decora_wifi API's session.login returns None, there was a problem with the credentials.
            if success is None:
                raise DecoraWifiLoginFailed
            self._loggedin = True
        except ValueError as exc:
            raise DecoraWifiCommFailed from exc

        self._loggedin = True

    def api_logout(self):
        """Log out of decora_wifi session."""
        if self._loggedin:
            try:
                Person.logout(self._session)
            except ValueError as exc:
                raise DecoraWifiCommFailed from exc
        self._loggedin = False

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
            raise DecoraWifiCommFailed from exc

    def reauth(self):
        """Reauthenticate this object's session."""
        self.api_logout()
        self._session = DecoraWiFiSession()
        self._api_login()

    def refresh_devices(self):
        """Refresh this object's devices."""
        self._iot_switches: dict[str, IotSwitch] = {
            platform: [] for platform in PLATFORMS
        }
        self._api_get_devices()

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


decorawifisessions: dict[str, DecoraWifiPlatform] = {}


class DecoraWifiEntity(Entity):
    """Initiate Decora Wifi Base Class."""

    def __init__(self, device):
        """Initialize Decora Wifi device base class."""
        self._switch = device
        self._unique_id = device.mac

    async def async_added_to_hass(self):
        """Run on addition of device to hass."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
