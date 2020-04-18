"""Config helpers for Alexa."""
from abc import ABC, abstractmethod

from homeassistant.core import callback

from .state_report import async_enable_proactive_mode


class AbstractConfig(ABC):
    """Hold the configuration for Alexa."""

    _unsub_proactive_report = None

    def __init__(self, hass):
        """Initialize abstract config."""
        self.hass = hass

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

    async def async_enable_proactive_mode(self):
        """Enable proactive mode."""
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
        unsub_func = await self._unsub_proactive_report
        if unsub_func:
            unsub_func()
        self._unsub_proactive_report = None

    @callback
    def should_expose(self, entity_id):
        """If an entity should be exposed."""
        # pylint: disable=no-self-use
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
