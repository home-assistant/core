"""API for google_sdm bound to Home Assistant OAuth."""
from asyncio import run_coroutine_threadsafe
import logging

from google_sdm import SDMAPI
from google_sdm.devices import SDMCamera, SDMDisplay, SDMDoorbell, SDMThermostat

from homeassistant import config_entries, core
from homeassistant.helpers import config_entry_oauth2_flow

from .climate import Climate

_LOGGER = logging.getLogger(__name__)


class ConfigEntryAuth(SDMAPI):
    """Provide google_sdm authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
        project_id: str,
        pubsub_auth,
        pubsub_subscription,
    ):
        """Initialize google_sdm Auth."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        super().__init__(
            self.session.token,
            project_id,
            pubsub_auth=pubsub_auth,
            pubsub_subscription=pubsub_subscription,
        )
        self.hass_devices = []

    def refresh_tokens(self) -> dict:
        """Refresh and return new google_sdm tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token

    def populate_devices(self):
        """Get a dictionary of devices."""
        devices = []
        for device in self.get_devices():
            if isinstance(device, SDMCamera):
                # device = Camera(self.hass, device)
                pass
            elif isinstance(device, SDMDisplay):
                # device = Display(self.hass, device)
                pass
            elif isinstance(device, SDMDoorbell):
                # device = Doorbell(self.hass, device)
                pass
            elif isinstance(device, SDMThermostat):
                device = Climate(device)
            else:
                _LOGGER.warning("Device type %s not implemented", device.type)
                continue
            devices.append(device)
        self.hass_devices = devices
        self.listen_events()
        return devices
