"""Config helpers for Alexa."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any

from yarl import URL

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .entities import TRANSLATION_TABLE
from .state_report import async_enable_proactive_mode

STORE_AUTHORIZED = "authorized"

_LOGGER = logging.getLogger(__name__)


class AbstractConfig(ABC):
    """Hold the configuration for Alexa."""

    _store: AlexaConfigStore
    _unsub_proactive_report: CALLBACK_TYPE | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize abstract config."""
        self.hass = hass
        self._enable_proactive_mode_lock = asyncio.Lock()
        self._on_deinitialize: list[CALLBACK_TYPE] = []

    async def async_initialize(self) -> None:
        """Perform async initialization of config."""
        self._store = AlexaConfigStore(self.hass)
        await self._store.async_load()

    @callback
    def async_deinitialize(self) -> None:
        """Remove listeners."""
        _LOGGER.debug("async_deinitialize")
        while self._on_deinitialize:
            self._on_deinitialize.pop()()

    @property
    def supports_auth(self) -> bool:
        """Return if config supports auth."""
        return False

    @property
    def should_report_state(self) -> bool:
        """Return if states should be proactively reported."""
        return False

    @property
    @abstractmethod
    def endpoint(self) -> str | URL | None:
        """Endpoint for report state."""

    @property
    @abstractmethod
    def locale(self) -> str | None:
        """Return config locale."""

    @property
    def entity_config(self) -> dict[str, Any]:
        """Return entity config."""
        return {}

    @property
    def is_reporting_states(self) -> bool:
        """Return if proactive mode is enabled."""
        return self._unsub_proactive_report is not None

    @callback
    @abstractmethod
    def user_identifier(self) -> str:
        """Return an identifier for the user that represents this config."""

    async def async_enable_proactive_mode(self) -> None:
        """Enable proactive mode."""
        _LOGGER.debug("Enable proactive mode")
        async with self._enable_proactive_mode_lock:
            if self._unsub_proactive_report is not None:
                return
            self._unsub_proactive_report = await async_enable_proactive_mode(
                self.hass, self
            )

    async def async_disable_proactive_mode(self) -> None:
        """Disable proactive mode."""
        _LOGGER.debug("Disable proactive mode")
        if unsub_func := self._unsub_proactive_report:
            unsub_func()
        self._unsub_proactive_report = None

    @callback
    def should_expose(self, entity_id: str) -> bool:
        """If an entity should be exposed."""
        return False

    def generate_alexa_id(self, entity_id: str) -> str:
        """Return the alexa ID for an entity ID."""
        return entity_id.replace(".", "#").translate(TRANSLATION_TABLE)

    @callback
    def async_invalidate_access_token(self) -> None:
        """Invalidate access token."""
        raise NotImplementedError

    async def async_get_access_token(self) -> str | None:
        """Get an access token."""
        raise NotImplementedError

    async def async_accept_grant(self, code: str) -> str | None:
        """Accept a grant."""
        raise NotImplementedError

    @property
    def authorized(self) -> bool:
        """Return authorization status."""
        return self._store.authorized

    async def set_authorized(self, authorized: bool) -> None:
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

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a configuration store."""
        self._data: dict[str, Any] | None = None
        self._hass = hass
        self._store: Store = Store(hass, self._STORAGE_VERSION, self._STORAGE_KEY)

    @property
    def authorized(self) -> bool:
        """Return authorization status."""
        assert self._data is not None
        return bool(self._data[STORE_AUTHORIZED])

    @callback
    def set_authorized(self, authorized: bool) -> None:
        """Set authorization status."""
        if self._data is not None and authorized != self._data[STORE_AUTHORIZED]:
            self._data[STORE_AUTHORIZED] = authorized
            self._store.async_delay_save(lambda: self._data, 1.0)

    async def async_load(self) -> None:
        """Load saved configuration from disk."""
        if data := await self._store.async_load():
            self._data = data
        else:
            self._data = {STORE_AUTHORIZED: False}
