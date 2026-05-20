"""Utilities to support zeroconf discovery of new plugs on the network.

Architecture note
-----------------
Powersensor uses a hub-and-spoke model: one or more physical *gateways*
(smart plugs) are discovered via mDNS/zeroconf.  Each gateway relays UDP
push messages from multiple wireless electricity/water *sensors* attached to
individual circuits.  A single config entry therefore owns the whole
household, which is why the manifest declares ``single_config_entry: true``.

Why zeroconf with a single config entry?
----------------------------------------
Despite having only one config entry, there can be many plugs (and therefore
many zeroconf service records), and plugs can appear or disappear at any time
as they power-cycle or move on the network.  Continuous mDNS browsing is
therefore necessary to:

- Detect new plugs that come online after initial setup (e.g. the user adds
  a second gateway).
- Reconnect to a plug whose IP address changes (DHCP lease renewal).
- Debounce transient disappearances (e.g. plug rebooting) so that the user
  does not see unnecessary unavailability flashes.

Sensors are *not* directly discoverable — they communicate over low-power
radio to whichever plug is in range, which relays their data over UDP.  The
zeroconf layer therefore only tracks plugs; sensors are discovered implicitly
via ``now_relaying_for`` messages emitted by those plugs.

Thread-safety
-------------
``PowersensorServiceListener`` is called from the zeroconf background thread.
Because the zeroconf ``ServiceListener`` interface is always invoked from that
background thread (never from the HA event loop), no runtime thread detection
is needed — all HA-facing calls unconditionally cross the thread boundary.

Dispatcher signals use ``dispatcher_send``, the thread-safe sync counterpart to
``async_dispatcher_send`` (see HA docs: asyncio_thread_safety).

The ``@callback`` helpers ``_schedule_removal_on_loop`` and ``_cancel_on_loop``
have no sync wrapper, so they are scheduled via the standard Python primitive
``hass.loop.call_soon_threadsafe``, as recommended in the HA async docs.
"""

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from zeroconf import BadTypeInNameException, ServiceBrowser, ServiceListener

import homeassistant.components.zeroconf
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.event import async_call_later

from .const import (
    ZEROCONF_ADD_PLUG_SIGNAL,
    ZEROCONF_REMOVE_PLUG_SIGNAL,
    ZEROCONF_SERVICE_TYPE,
    ZEROCONF_UPDATE_PLUG_SIGNAL,
)

_LOGGER = logging.getLogger(__name__)


class PowersensorServiceListener(ServiceListener):
    """Zeroconf service listener that signals the HA dispatcher on plug changes.

    The ServiceListener interface is always invoked from the zeroconf background
    thread, so all HA-facing calls unconditionally cross the thread boundary:
    dispatcher signals via ``dispatcher_send``; ``@callback`` helpers via
    ``hass.loop.call_soon_threadsafe``.
    """

    def __init__(self, hass: HomeAssistant, debounce_timeout: float = 60) -> None:
        """Initialise the listener."""
        self._hass = hass
        self._plugs: dict[str, dict[str, Any]] = {}
        self._pending_removals: dict[str, Callable[[], None | bool]] = {}
        self._removed: set[str] = set()  # names that have been fully removed
        self._debounce_seconds = debounce_timeout

    # ------------------------------------------------------------------
    # ServiceListener interface (called from the zeroconf thread)
    # ------------------------------------------------------------------

    def add_service(self, zc: Any, type_: str, name: str) -> None:
        """Handle a new service announcement."""
        self._cancel_pending_removal(name, "request to add")
        if self._extract_plug_info(zc, type_, name):
            self._removed.discard(name)
            self.dispatch(ZEROCONF_ADD_PLUG_SIGNAL, self._plugs[name])

    def update_service(self, zc: Any, type_: str, name: str) -> None:
        """Handle a service update announcement."""
        self._cancel_pending_removal(name, "request to update")
        if self._extract_plug_info(zc, type_, name):
            self.dispatch(ZEROCONF_UPDATE_PLUG_SIGNAL, self._plugs[name])

    def remove_service(self, zc: Any, type_: str, name: str) -> None:
        """Handle a service removal announcement."""
        if name in self._pending_removals:
            _LOGGER.info("Removal for %s already pending", name)
            return  # already scheduled

        _LOGGER.info("Scheduling removal for %s", name)
        self._hass.loop.call_soon_threadsafe(self._schedule_removal_on_loop, name)

    # ------------------------------------------------------------------
    # Public dispatch helper
    # ------------------------------------------------------------------

    def dispatch(self, signal: str, *args: Any) -> None:
        """Send a dispatcher signal from the zeroconf thread.

        Uses ``dispatcher_send`` — the thread-safe sync counterpart to
        ``async_dispatcher_send`` — so no manual loop scheduling is needed.
        """
        dispatcher_send(self._hass, signal, *args)

    # ------------------------------------------------------------------
    # Event-loop-side helpers
    # ------------------------------------------------------------------

    @callback
    def _schedule_removal_on_loop(self, name: str) -> None:
        """Schedule the debounce timer. Must only be called on the event loop."""
        if name in self._pending_removals:
            return  # re-check now that we're on the loop
        if name in self._removed:
            return  # plug already removed by a prior timer — nothing to do

        @callback
        def _do_remove(_now: datetime) -> None:
            self._pending_removals.pop(name, None)
            _LOGGER.info(
                "Service %s still absent after timeout - processing removal", name
            )
            data = self._plugs.pop(name, None)
            self._removed.add(name)
            # Running on the event loop already — call async_dispatcher_send directly.
            async_dispatcher_send(self._hass, ZEROCONF_REMOVE_PLUG_SIGNAL, name, data)

        self._pending_removals[name] = async_call_later(
            self._hass, self._debounce_seconds, _do_remove
        )

    @callback
    def _cancel_on_loop(self, name: str, source: str) -> None:
        """Cancel a pending removal timer. Must only be called on the event loop."""
        cancel = self._pending_removals.pop(name, None)
        if cancel:
            cancel()
            _LOGGER.info("Cancelled pending removal for %s by %s", name, source)

    # ------------------------------------------------------------------
    # Private helpers (may be called from the zeroconf thread)
    # ------------------------------------------------------------------

    def _cancel_pending_removal(self, name: str, source: str) -> None:
        """Cancel a pending removal timer from the zeroconf thread."""
        if name not in self._pending_removals:
            return
        self._hass.loop.call_soon_threadsafe(self._cancel_on_loop, name, source)

    def _extract_plug_info(self, zc: Any, type_: str, name: str) -> bool:
        """Populate ``self._plugs[name]`` from the zeroconf record.

        Returns True on success, False if the record could not be retrieved.
        """
        try:
            info = zc.get_service_info(type_, name)
        except (BadTypeInNameException, OSError, NotImplementedError) as err:
            _LOGGER.error("Error retrieving info for %s: %s", name, err)
            return False

        if not info:
            return False

        self._plugs[name] = {
            "type": type_,
            "name": name,
            "addresses": info.parsed_addresses(),
            "port": info.port,
            "server": info.server,
            "properties": info.properties,
        }
        return True


class PowersensorDiscoveryService:
    """Manages the lifecycle of the zeroconf service browser for Powersensor plugs."""

    def __init__(
        self,
        hass: HomeAssistant,
        service_type: str = ZEROCONF_SERVICE_TYPE,
    ) -> None:
        """Initialise the discovery service."""
        self._hass = hass
        self.service_type = service_type
        self.listener: PowersensorServiceListener | None = None
        self.browser: ServiceBrowser | None = None
        self.running = False

    async def start(self) -> None:
        """Start the mDNS service browser.

        Uses the shared HA zeroconf instance — no separate keepalive task
        or ``asyncio.sleep`` loop is required; the browser is event-driven.
        """
        if self.running:
            return

        self.running = True
        zc = await homeassistant.components.zeroconf.async_get_instance(self._hass)
        self.listener = PowersensorServiceListener(self._hass)
        self.browser = ServiceBrowser(zc, self.service_type, self.listener)

    async def stop(self) -> None:
        """Stop the service browser and release resources."""
        self.running = False

        if self.browser is not None:
            self.browser.cancel()
            self.browser = None

        self.listener = None
