"""Common code for decora_wifi."""

from __future__ import annotations

import logging
from typing import Callable

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount
from decora_wifi.models.residential_permission import ResidentialPermission

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import LIGHT_DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


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


class DecoraWifiPlatform:
    """Class to hold decora_wifi platform sessions and related methods."""

    def __init__(self, hass: HomeAssistant, email: str, password: str) -> None:
        """Iniialize session holder."""
        self._hass = hass
        self._session = None
        self._email = email
        self._name = f"Decora_Wifi - {self._email}"
        self._password = password
        self._iot_switches: dict[str, IotSwitch] = {}
        self._logged_in = False
        self._remove_stop_listener: Callable | None = None

    @property
    def active_platforms(self) -> list[str]:
        """Get the list of platforms which have devices defined."""
        return [p for p in PLATFORMS if self._iot_switches[p]]

    @property
    def email(self) -> str:
        """Get the user id (email) associated with this session."""
        return self._email

    @property
    def lights(self) -> list[IotSwitch]:
        """Get the lights."""
        return self._iot_switches[LIGHT_DOMAIN]

    def _api_login(self):
        """Log in to decora_wifi session."""
        try:
            user = self._session.login(self._email, self._password)
            # If the call to the decora_wifi API's session.login returns None, there was a problem with the credentials.
            if user is None:
                raise LoginFailed
        except ValueError as exc:
            self._logged_in = False
            raise CommFailed from exc
        self._logged_in = True

    def _api_logout(self):
        """Log out of decora_wifi session."""
        if self._logged_in:
            try:
                Person.logout(self._session)
            except ValueError as exc:
                raise CommFailed from exc
        self._logged_in = False

    def _api_get_devices(self):
        """Update the device library from the API."""
        perms: list[ResidentialPermission] = []
        accounts: list[ResidentialAccount] = []
        residences: list[Residence] = []
        switches: list[IotSwitch] = []

        # Gather permissions
        try:
            perms.extend(self._session.user.get_residential_permissions())
        except ValueError as exc:
            self._logged_in = False
            raise CommFailed from exc

        # Gather residences for which the logged in user has permissions
        for permission in perms:
            if permission.residentialAccountId is not None:
                accounts.append(
                    ResidentialAccount(self._session, permission.residentialAccountId)
                )
            elif permission.residenceId is not None:
                residences.append(Residence(self._session, permission.residenceId))
        for acct in accounts:
            try:
                residences.extend(acct.get_residences())
            except ValueError as exc:
                raise CommFailed from exc

        # Gather switches from residences
        for res in residences:
            try:
                switches.extend(res.get_iot_switches())
            except ValueError as exc:
                raise CommFailed from exc

        # Add the switches to the appropriate list in the iot_switches dictionary.
        for switch in switches:
            platform = DecoraWifiPlatform.classify_device(switch)
            self._iot_switches[platform].append(switch)

    def _set_stop_listener(self):
        """Set up a bus listener to logout on EVENT_HOMEASSISTANT_STOP."""

        def logout(event):
            """Log out."""
            try:
                self.teardown()
            except CommFailed:
                _LOGGER.debug(
                    "Communication with myLeviton failed while attempting to logout"
                )

        self._remove_stop_listener = self._hass.bus.listen(
            EVENT_HOMEASSISTANT_STOP, logout
        )

    def refresh_devices(self):
        """Refresh this object's devices."""
        self._iot_switches: dict[str, IotSwitch] = {
            platform: [] for platform in PLATFORMS
        }
        self._api_get_devices()

    def setup(self):
        """Set up the session after object instantiation."""
        self._iot_switches = {platform: [] for platform in PLATFORMS}
        self._session = DecoraWiFiSession()
        self._api_login()
        self._set_stop_listener()
        self._api_get_devices()

    def teardown(self):
        """Clean up the session in preparation for object deletion."""
        self._api_logout()
        # Clean up the stop listener if it is set.
        if self._remove_stop_listener:
            self._remove_stop_listener()
            self._remove_stop_listener = None

    @staticmethod
    async def async_setup_decora_wifi(hass: HomeAssistant, email: str, password: str):
        """Set up a decora wifi session."""

        def setup_platform() -> DecoraWifiPlatform:
            platform = DecoraWifiPlatform(hass, email, password)
            platform.setup()
            return platform

        return await hass.async_add_executor_job(setup_platform)

    @staticmethod
    def classify_device(dev):
        """Classify devices by platform."""
        # The light platform is the only one currently implemented in the integration.
        return LIGHT_DOMAIN


class DecoraWifiEntity(Entity):
    """Base Class for decora_wifi entities."""

    def __init__(self, device: IotSwitch) -> None:
        """Initialize Decora Wifi device base class."""
        self._switch = device
        self._model = self._switch.model
        self._mac_address = self._switch.mac
        self._attr_name = self._switch.name
        self._attr_unique_id = self._mac_address
        self._attr_device_info = DeviceInfo(
            name=self._switch.name,
            connections={(device_registry.CONNECTION_NETWORK_MAC, self._mac_address)},
            manufacturer=self._switch.manufacturer,
            model=self._model,
            sw_version=self._switch.version,
        )
