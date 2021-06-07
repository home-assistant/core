"""Common code for decora_wifi."""

import logging
from typing import Dict

# pylint: disable=import-error
from decora_wifi import DecoraWiFiSession
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LIGHT_DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class DecoraWifiPlatform:
    """Class to hold the decora_wifi platform sessions and methods."""

    _sessions: Dict[str, DecoraWiFiSession] = {}

    @staticmethod
    async def async_login(hass, email, password):
        """Log in a Decora Wifi session."""
        session = DecoraWiFiSession()

        def trylogin():
            success = session.login(email, password)
            return success

        try:
            success = await hass.async_add_executor_job(trylogin)

            # If login failed, notify user.
            if success is None:
                msg = "Failed to log into myLeviton Services. Check credentials."
                _LOGGER.error(msg)
                raise DecoraWifiLoginFailed

        except ValueError as exc:
            _LOGGER.error("Failed to communicate with myLeviton Service")
            raise DecoraWifiCommFailed from exc

        # Add the created session to the sessions dict.
        DecoraWifiPlatform._sessions.update({email: session})

        # Indicate success by returning true.
        return True

    @staticmethod
    async def async_logout(hass, email):
        """Log out of decora_wifi session."""
        session = DecoraWifiPlatform._sessions.pop(email, None)

        def trylogout():
            Person.logout(session)
            return True

        try:
            if session is not None:
                await hass.async_add_executor_job(trylogout)
            else:
                raise DecoraWifiSessionNotFound
        except ValueError:
            _LOGGER.error("Failed to log out of myLeviton Service.")

    @staticmethod
    async def async_getdevices(hass, email):
        """Get devices from the Decora Wifi service."""
        session = DecoraWifiPlatform._sessions.get(email, None)
        if session is None:
            raise DecoraWifiSessionNotFound

        iot_switches = {platform: [] for platform in PLATFORMS}

        try:
            # Gather all the available devices into the iot_switches dictionary...
            perms = await hass.async_add_executor_job(
                session.user.get_residential_permissions
            )
            for permission in perms:
                if permission.residentialAccountId is not None:
                    acct = ResidentialAccount(session, permission.residentialAccountId)
                    residences = await hass.async_add_executor_job(acct.get_residences)
                    for r in residences:
                        switches = await hass.async_add_executor_job(r.get_iot_switches)
                        for s in switches:
                            # Add the switch to the appropriate list in the iot_switches dictionary.
                            iot_switches[DecoraWifiPlatform.classifydevice(s)].append(s)
                elif permission.residenceId is not None:
                    residence = Residence(session, permission.residenceId)
                    switches = await hass.async_add_executor_job(
                        residence.get_iot_switches
                    )
                    for s in switches:
                        # Add the switch to the appropriate list in the iot_switches dictionary.
                        iot_switches[DecoraWifiPlatform.classifydevice(s)].append(s)

        except ValueError as exc:
            _LOGGER.error("Failed to communicate with myLeviton Service")
            raise DecoraWifiCommFailed from exc

        return iot_switches

    @staticmethod
    def classifydevice(dev):
        """Sort devices by device type."""
        return LIGHT_DOMAIN


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


class DecoraWifiLoginFailed(Exception):
    """Raised when DecoraWifiPlatform.login() fails to log in."""

    pass


class DecoraWifiCommFailed(Exception):
    """Raised when DecoraWifiPlatform.login() fails to communicate with the myLeviton Service."""

    pass


class DecoraWifiSessionNotFound(Exception):
    """Raised when DecoraWifi fails to find a session in the sessions dictionary."""

    pass
