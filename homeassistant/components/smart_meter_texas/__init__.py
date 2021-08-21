"""The Smart Meter Texas integration."""
import asyncio
import logging
import ssl
import socket
import OpenSSL.crypto as crypto
import certifi
import re
import urllib

from smart_meter_texas import Account, Client
from smart_meter_texas.exceptions import (
    SmartMeterTexasAPIError,
    SmartMeterTexasAuthError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    Debouncer,
    UpdateFailed,
)

from .const import (
    BASE_HOSTNAME,
    DATA_COORDINATOR,
    DATA_SMART_METER,
    DEBOUNCE_COOLDOWN,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Meter Texas from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    account = Account(username, password)

    sslContext = None

    try:
        """ Attempt to retrieve the CA Issuers file and load it into the SSL Context"""
        caiKey = 'CA Issuers - URI:'
        reIssuersURI = re.compile(r"(https?://+[\w\d:#@%/;$()~_?\+-=\\\.&]*)", re.UNICODE)
        caIssuersURI = None
        sslContext = ssl.create_default_context(capath=certifi.where())
        sslContext.check_hostname = False
        sslContext.verify_mode = ssl.CERT_NONE
        with sslContext.wrap_socket(socket.socket(), server_hostname=BASE_HOSTNAME) as s:
            s.connect((BASE_HOSTNAME, 443))
            cert_bin = s.getpeercert(True)
            x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_bin)
            for idx in range(x509.get_extension_count()):
                ext = x509.get_extension(idx)
                short_name = ext.get_short_name()
                if short_name == b"authorityInfoAccess":
                    authorityInfoAccess = str(ext)
                    caiIndx = authorityInfoAccess.find(caiKey)
                    if (caiIndx > -1):
                        caiValue = authorityInfoAccess[caiIndx:]
                        caIssuersURI = reIssuersURI.findall(caiValue)[0]

        if (caIssuersURI != None):
            with urllib.request.urlopen(caIssuersURI) as certReq:
                certData = certReq.read()
                sslContext.load_verify_locations(cafile=certifi.where(), cadata = certData)

        # Re-enable strict checking
        sslContext.check_hostname = True
        sslContext.verify_mode = ssl.CERT_REQUIRED
        sslContext.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_SSLv3 | ssl.OP_NO_SSLv2
    except:
        _LOGGER.error("Failure in establishing ssl context with retrieved CA Issuers file.")
        sslContext = None

    smart_meter_texas_data = SmartMeterTexasData(hass, entry, account, sslContext)
    try:
        await smart_meter_texas_data.client.authenticate()
    except SmartMeterTexasAuthError:
        _LOGGER.error("Username or password was not accepted")
        return False
    except asyncio.TimeoutError as error:
        raise ConfigEntryNotReady from error

    await smart_meter_texas_data.setup()

    async def async_update_data():
        _LOGGER.debug("Fetching latest data")
        await smart_meter_texas_data.read_meters()
        return smart_meter_texas_data

    # Use a DataUpdateCoordinator to manage the updates. This is due to the
    # Smart Meter Texas API which takes around 30 seconds to read a meter.
    # This avoids Home Assistant from complaining about the component taking
    # too long to update.
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Smart Meter Texas",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_COOLDOWN, immediate=True
        ),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_SMART_METER: smart_meter_texas_data,
    }

    asyncio.create_task(coordinator.async_refresh())

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class SmartMeterTexasData:
    """Manages coordinatation of API data updates."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, account: Account, ssl: ssl.SSLContext
    ) -> None:
        """Initialize the data coordintator."""
        self._entry = entry
        self.account = account
        self.sslContext = ssl
        websession = aiohttp_client.async_get_clientsession(hass)
        self.client = Client(websession, account, sslcontext=self.sslContext)
        self.meters: list = []

    async def setup(self):
        """Fetch all of the user's meters."""
        self.meters = await self.account.fetch_meters(self.client)
        _LOGGER.debug("Discovered %s meter(s)", len(self.meters))

    async def read_meters(self):
        """Read each meter."""
        for meter in self.meters:
            try:
                await meter.read_meter(self.client)
            except (SmartMeterTexasAPIError, SmartMeterTexasAuthError) as error:
                raise UpdateFailed(error) from error
        return self.meters


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
