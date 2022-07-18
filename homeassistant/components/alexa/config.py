"""Config helpers for Alexa."""
from abc import ABC, abstractmethod
import logging

from homeassistant.core import callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .state_report import async_enable_proactive_mode

STORE_AUTHORIZED = "authorized"

_LOGGER = logging.getLogger(__name__)


class AbstractConfig(ABC):
    """Hold the configuration for Alexa."""

    _unsub_proactive_report = None

    def __init__(self, hass):
        """Initialize abstract config."""
        self.hass = hass
        self._store = None

    async def async_initialize(self):
        """Perform async initialization of config."""
        self._store = AlexaConfigStore(self.hass)
        await self._store.async_load()

    @property
    def supports_auth(self):
        """Return if config supports auth."""
        return False

    @property
    def should_report_state(self):
        """Return if states should be proactively reported."""
        return False

    @property
    def endpoint(self):
        """Endpoint for report state."""
        return None

    @property
    @abstractmethod
    def locale(self):
        """Return config locale."""

    @property
    def entity_config(self):
        """Return entity config."""
        return {}

    @property
    def is_reporting_states(self):
        """Return if proactive mode is enabled."""
        return self._unsub_proactive_report is not None

    @callback
    @abstractmethod
    def user_identifier(self):
        """Return an identifier for the user that represents this config."""

    async def async_enable_proactive_mode(self):
        """Enable proactive mode."""
        _LOGGER.debug("Enable proactive mode")
        if self._unsub_proactive_report is None:
            self._unsub_proactive_report = self.hass.async_create_task(
                async_enable_proactive_mode(self.hass, self)
            )
        try:
            await self._unsub_proactive_report
        except Exception:
            self._unsub_proactive_report = None
            raise

    async def async_disable_proactive_mode(self):
        """Disable proactive mode."""
        _LOGGER.debug("Disable proactive mode")
        if unsub_func := await self._unsub_proactive_report:
            unsub_func()
        self._unsub_proactive_report = None

    @callback
    def should_expose(self, entity_id):
        """If an entity should be exposed."""
        return False

    @callback
    def async_invalidate_access_token(self):
        """Invalidate access token."""
        raise NotImplementedError

    async def async_get_access_token(self):
        """Get an access token."""
        raise NotImplementedError

    async def async_accept_grant(self, code):
        """Accept a grant."""
        raise NotImplementedError

    @property
    def authorized(self):
        """Return authorization status."""
        return self._store.authorized

    async def set_authorized(self, authorized):
        """Set authorization status.

        - Set when an incoming message is received from Alexa.
        - Unset if state reporting fails
        """
        self._store.set_authorized(authorized)
        if self.should_report_state != self.is_reporting_states:
            if self.should_report_state:
                try:
                    await self.async_enable_proactive_mode()
                except Exception:
                    # We failed to enable proactive mode, unset authorized flag
                    self._store.set_authorized(False)
                    raise
            else:
                await self.async_disable_proactive_mode()


class AlexaConfigStore:
    """A configuration store for Alexa."""

    _STORAGE_VERSION = 1
    _STORAGE_KEY = DOMAIN

    def __init__(self, hass):
        """Initialize a configuration store."""
        self._data = None
        self._hass = hass
        self._store = Store(hass, self._STORAGE_VERSION, self._STORAGE_KEY)

    @property
    def authorized(self):
        """Return authorization status."""
        return self._data[STORE_AUTHORIZED]

    @callback
    def set_authorized(self, authorized):
        """Set authorization status."""
        if authorized != self._data[STORE_AUTHORIZED]:
            self._data[STORE_AUTHORIZED] = authorized
            self._store.async_delay_save(lambda: self._data, 1.0)

    async def async_load(self):
        """Load saved configuration from disk."""
        if data := await self._store.async_load():
            self._data = data
        else:
            self._data = {STORE_AUTHORIZED: False}
