import base64
from datetime import timedelta
import json
import logging

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA  # cryptodome
import requests

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
    DOMAIN as TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .helpers import decrypt_response, encrypt_request

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

class Zyxel_T50_Router(object):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry

        self.url = entry.data[CONF_HOST]
        self.user = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]

        self.r = requests.Session()
        self.r.trust_env = False # ignore proxy settings

        # we define the AesKey ourselves
        self.aes_key = b'\x42'*32
        self.enc_aes_key = None
        self.sessionkey = None

        self._model = None
        self._sw_version = None
        self._unique_id = None

        self._devices: dict[str, ZyxelDevice] = {}
        self._connected_devices = 0

        self._on_close = []

    async def setup(self) -> None:
        """Set up a Zyxel router."""
        self.enc_aes_key = await self.get_aes_key()

        try:
            await self.perform_login()
        except CannotConnect as exp:
            _LOGGER.error("Failed to connect to router")
            raise ConfigEntryNotReady from exp

        status = await self.get_device_status()

        device_info = status["DeviceInfo"]
        if self._unique_id is None:
            self._unique_id = device_info["SerialNumber"]

        self._model = device_info["ModelName"]
        self._sw_version = device_info["SoftwareVersion"]

        # Load tracked entities from registry
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        track_entries = (
            self.hass.helpers.entity_registry.async_entries_for_config_entry(
                entity_registry, self._entry.entry_id
            )
        )
        for entry in track_entries:
            if entry.domain == TRACKER_DOMAIN:
                self._devices[entry.unique_id] = ZyxelDevice(entry.unique_id, entry.original_name)

        # Update devices
        await self.update_devices()

        self.async_on_close(
            async_track_time_interval(self.hass, self.update_all, SCAN_INTERVAL)
        )

    async def close(self) -> None:
        """Close the connection."""
        await self.perform_logout()

        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    async def update_all(self, now) -> None:
        """Update all Zyxel platforms."""
        await self.update_devices()

    async def update_devices(self) -> None:
        new_device = False

        zyxel_devices = await self.get_connected_devices()
        consider_home = DEFAULT_CONSIDER_HOME.total_seconds()

        # TODO hide unknown devices
        # track_unknown = self._options.get(CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN)

        for device_mac in self._devices:
            dev_info = zyxel_devices.get(device_mac)
            self._devices[device_mac].update(dev_info, consider_home)

        for device_mac, dev_info in zyxel_devices.items():
            if device_mac in self._devices:
                continue
            # if not track_unknown and not dev_info.name:
            #     continue
            new_device = True
            device = ZyxelDevice(device_mac)
            device.update(dev_info)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

        self._connected_devices = len(zyxel_devices)

    @property
    def signal_device_new(self) -> str:
        """Event specific per Zyxel entry to signal new device."""
        return f"{DOMAIN}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Zyxel entry to signal updates in devices."""
        return f"{DOMAIN}-device-update"

    async def get_aes_key(self):
        # ONCE
        # get pub key
        response = await self.hass.async_add_executor_job(self.r.get, f"http://{self.url}/getRSAPublickKey")
        pubkey_str = response.json()['RSAPublicKey']

        # Encrypt the aes key with RSA pubkey of the device
        pubkey = RSA.import_key(pubkey_str)
        cipher_rsa = PKCS1_v1_5.new(pubkey)
        return cipher_rsa.encrypt(base64.b64encode(self.aes_key))

    async def perform_login(self):
        login_data = {
            "Input_Account": self.user,
            "Input_Passwd": base64.b64encode(self.password.encode('ascii')).decode('ascii'),
            "RememberPassword": 0,
            "SHA512_password": False
        }

        enc_request = encrypt_request(self.aes_key, login_data)
        enc_request['key'] = base64.b64encode(self.enc_aes_key).decode('ascii')
        response = await self.hass.async_add_executor_job(self.r.post, f"http://{self.url}/UserLogin", json.dumps(enc_request))
        decrypted_response = decrypt_response(self.aes_key, response.json())

        if decrypted_response is not None:
            response = json.loads(decrypted_response)

            self.sessionkey = response['sessionkey']
            return 'result' in response and response['result'] == 'ZCFG_SUCCESS'

        _LOGGER.error("Failed to decrypt response")
        raise CannotConnect

    async def perform_logout(self):
        response = await self.hass.async_add_executor_job(self.r.post, f"http://{self.url}/cgi-bin/UserLogout?sessionKey={self.sessionkey}")
        response = response.json()

        if 'result' in response and response['result'] == 'ZCFG_SUCCESS':
            return True
        else:
            return False

    async def get_device_info(self, oid):
        response = await self.hass.async_add_executor_job(self.r.get, f"http://{self.url}/cgi-bin/DAL?oid={oid}")
        decrypted_response = decrypt_response(self.aes_key, response.json())
        if decrypted_response is not None:
            json_string = decrypted_response.decode('utf8').replace("'", '"')
            json_data = json.loads(json_string)
            return json_data['Object'][0]

        _LOGGER.error("Failed to get device status")
        return None

    # TODO Add sensors for various status items
    async def get_device_status(self):
        result = await self.get_device_info("cardpage_status")
        if result is not None:
            return result

        _LOGGER.error("Failed to get device status")
        return None

    async def get_connected_devices(self):
        result = await self.get_device_info("lanhosts")
        if result is not None:
            devices = {}
            for device in result['lanhosts']:
                devices[device['PhysAddress']] = {
                    "host_name": device['HostName'],
                    "phys_address": device['PhysAddress'],
                    "ip_address": device['IPAddress'],
                }
            return devices

        _LOGGER.error("Failed to connected devices")
        return []

    @property
    def devices(self):
        """Return devices."""
        return self._devices

class ZyxelDevice:
    """Representation of a Zyxel device info."""

    def __init__(self, mac, name=None):
        """Initialize a Zyxel device info."""
        self._mac = mac
        self._name = name
        self._ip_address = None
        self._last_activity = None
        self._connected = False

    def update(self, dev_info=None, consider_home=0):
        """Update Zyxel device info."""
        utc_point_in_time = dt_util.utcnow()
        if dev_info:
            if not self._name:
                self._name = dev_info["host_name"] or self._mac.replace(":", "_")
            self._ip_address = dev_info["ip_address"]
            self._last_activity = utc_point_in_time
            self._connected = True

        elif self._connected:
            self._connected = (utc_point_in_time - self._last_activity).total_seconds() < consider_home
            self._ip_address = None

    @property
    def is_connected(self):
        """Return connected status."""
        return self._connected

    @property
    def mac(self):
        """Return device mac address."""
        return self._mac

    @property
    def name(self):
        """Return device name."""
        return self._name

    @property
    def ip_address(self):
        """Return device ip address."""
        return self._ip_address

    @property
    def last_activity(self):
        """Return device last activity."""
        return self._last_activity

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

