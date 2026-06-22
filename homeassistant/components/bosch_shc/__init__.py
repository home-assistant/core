"""The Bosch Smart Home Controller integration."""

from datetime import timedelta, time as dt_time

import voluptuous as vol
import inspect

from boschshcpy import SHCSessionAsync, SHCUniversalSwitch
from boschshcpy.api_async import build_ssl_context
from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
)

from .certificate import parse_certificate
from .data import SHCData
from homeassistant.components.persistent_notification import (
    async_create as pn_async_create,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ID,
    ATTR_NAME,
    ATTR_COMMAND,
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    ServiceResponse,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_EVENT_SUBTYPE,
    ATTR_EVENT_TYPE,
    ATTR_LAST_TIME_TRIGGERED,
    ATTR_SERVICE_ID,
    ATTR_TITLE,
    CERT_EXPIRY_WARNING_DAYS,
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN_NOTIFICATION_ID,
    DATA_CERT_CHECK_UNSUB,
    DATA_POLLING_HANDLER,
    DATA_SESSION,
    DATA_SHC,
    DATA_TITLE,
    DOMAIN,
    EVENT_BOSCH_SHC,
    LOGGER,
    OPT_ENABLE_RAWSCAN,
    OPT_LONG_POLL_TIMEOUT,
    OPT_CHILD_LOCK_ENABLED,
    OPT_PRESENCE_ENTITY,
    OPT_SSL_SKIP_VERIFY,
    OPT_SILENT_MODE_ENABLED,
    OPT_SILENT_MODE_START,
    OPT_SILENT_MODE_END,
    SERVICE_TRIGGER_SCENARIO,
    SERVICE_TRIGGER_RAWSCAN,
    SUPPORTED_INPUTS_EVENTS_TYPES,
)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
if hasattr(Platform, "VALVE"):
    PLATFORMS.append(Platform.VALVE)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bosch SHC component.

    The trigger_scenario service is registered here so it exists even when a
    config entry fails to load, allowing HA to validate automations that
    reference it.  The trigger_rawscan service is opt-in and registered per
    entry in async_setup_entry (default: enabled).  Entity services
    (smokedetector_check, smokedetector_alarmstate) are registered per-entry in
    their respective platform setup (binary_sensor.py) as allowed by the rule.
    """

    SCENARIO_TRIGGER_SCHEMA = vol.Schema(
        {
            vol.Optional(ATTR_TITLE, default=""): cv.string,
            vol.Required(ATTR_NAME): cv.string,
        }
    )

    async def scenario_service_call(call: ServiceCall) -> None:
        """SHC Scenario service call."""
        from boschshcpy.exceptions import SHCException, SHCConnectionError
        name = call.data[ATTR_NAME]
        title = call.data[ATTR_TITLE]
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if not hasattr(config_entry, "runtime_data"):
                continue
            runtime: SHCData = config_entry.runtime_data
            if title in ("", runtime.title):
                for scenario in runtime.session.scenarios:
                    if scenario.name == name:
                        try:
                            await scenario.async_trigger()
                        except (SHCException, SHCConnectionError) as err:
                            raise ServiceValidationError(
                                f"Failed to trigger scenario '{name}': {err}"
                            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIGGER_SCENARIO,
        scenario_service_call,
        SCENARIO_TRIGGER_SCHEMA,
    )

    return True


def _register_rawscan_service(hass: HomeAssistant) -> None:
    """Register the trigger_rawscan service if not already registered."""
    if hass.services.has_service(DOMAIN, SERVICE_TRIGGER_RAWSCAN):
        return

    RAWSCAN_TRIGGER_SCHEMA = vol.Schema(
        {
            vol.Optional(ATTR_TITLE, default=""): cv.string,
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_DEVICE_ID, default=""): cv.string,
            vol.Optional(ATTR_SERVICE_ID, default=""): cv.string,
        }
    )

    async def rawscan_service_call(call: ServiceCall) -> ServiceResponse:
        """SHC Rawscan service call."""
        title = call.data[ATTR_TITLE]
        command = call.data[ATTR_COMMAND]
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if not hasattr(config_entry, "runtime_data"):
                continue
            runtime: SHCData = config_entry.runtime_data
            if title in ("", runtime.title):
                api = runtime.session.api
                device_id = call.data[ATTR_DEVICE_ID]
                service_id = call.data[ATTR_SERVICE_ID]
                # SHCSessionAsync has no rawscan(); dispatch directly over the
                # async API (mirrors SHCSession.rawscan_commands).
                commands = {
                    "devices": api.get_devices,
                    "device": lambda: api.get_device(device_id),
                    "services": api.get_services,
                    "device_services": lambda: api.get_device_services(device_id),
                    "device_service": lambda: api.get_device_service(
                        device_id, service_id
                    ),
                    "rooms": api.get_rooms,
                    "scenarios": api.get_scenarios,
                    "messages": api.get_messages,
                    "info": api.get_information,
                    "information": api.get_information,
                    "public_information": api.get_public_information,
                    "intrusion_detection": api.get_domain_intrusion_detection,
                }
                if command not in commands:
                    raise ServiceValidationError(
                        f"Unknown rawscan command '{command}'. "
                        f"Valid commands: {sorted(commands)}"
                    )
                rawscan = await commands[command]()
                return {command: rawscan}

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIGGER_RAWSCAN,
        rawscan_service_call,
        schema=RAWSCAN_TRIGGER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bosch SHC from a config entry."""
    data = entry.data

    # Pre-flight certificate validity check for clearer user feedback
    cert_path = data.get(CONF_SSL_CERTIFICATE, "")
    try:
        cert_info = (
            await hass.async_add_executor_job(parse_certificate, cert_path)
            if cert_path
            else None
        )
    except Exception as err:  # broad: parsing issues shouldn't fully block reauth paths
        LOGGER.warning("Unable to parse Bosch SHC certificate (%s): %s", cert_path, err)
        cert_info = None

    if cert_info is not None:
        if cert_info.days_remaining < 0:
            expiry = cert_info.not_after.date()
            LOGGER.error(
                "Bosch SHC client certificate expired on %s. Reconfigure integration (put controller in pairing mode and re-authenticate).",
                expiry,
            )
            raise ConfigEntryAuthFailed(
                f"Client certificate expired on {expiry}. Reconfigure the integration."
            )
        if cert_info.days_remaining <= CERT_EXPIRY_WARNING_DAYS:
            expiry = cert_info.not_after.date()
            LOGGER.warning(
                "Bosch SHC client certificate will expire in %d days (on %s). Put controller in pairing mode and reconfigure integration to renew.",
                cert_info.days_remaining,
                expiry,
            )
            pn_async_create(
                hass,
                (
                    f"Bosch SHC client certificate will expire in {cert_info.days_remaining} days (on {expiry}).\n"
                    "To renew: Put the controller into pairing mode (press front button until LEDs flash) and start re-authentication from the integration options."
                ),
                title="Bosch SHC certificate expiring",
                notification_id=DOMAIN_NOTIFICATION_ID,
            )

    # NumberSelector yields a float; the SHC long-poll RPC expects an integer
    # number of seconds, so coerce it.
    long_poll_timeout = int(entry.options.get(OPT_LONG_POLL_TIMEOUT, 10))
    # Async migration (phase 3b): the integration runs SHCSessionAsync — aiohttp
    # I/O + an asyncio.Task long-poll, no thread, no executor. Construction does
    # NO network I/O; async_init() enumerates the device model on the loop.
    # TODO(async parity): SHCAPIAsync does not yet honor verify_hostname /
    # ssl_verify (#264 skip-SSL is sync-only) — port those into SHCAPIAsync.
    if entry.options.get(OPT_SSL_SKIP_VERIFY, False):
        LOGGER.warning(
            "ssl_skip_verify is set but is not yet honored on the async path; "
            "the bundled Bosch CA is still used. Tracked for async parity."
        )
    # Build the mTLS SSLContext off the event loop — it reads the cert/key/CA
    # PEM files (blocking I/O) — then hand it to the session so construction on
    # the loop stays non-blocking. Guard for older libs lacking the kwarg.
    _session_kwargs = {"long_poll_timeout": long_poll_timeout}
    if "ssl_context" in inspect.signature(SHCSessionAsync.__init__).parameters:
        _session_kwargs["ssl_context"] = await hass.async_add_executor_job(
            build_ssl_context,
            data[CONF_SSL_CERTIFICATE],
            data[CONF_SSL_KEY],
        )
    session = SHCSessionAsync(
        data[CONF_HOST],
        data[CONF_SSL_CERTIFICATE],
        data[CONF_SSL_KEY],
        **_session_kwargs,
    )
    try:
        await session.async_init()
    except SHCAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except SHCConnectionError as err:
        LOGGER.warning(
            "Bosch SHC at %s is unavailable, will retry: %s", data.get(CONF_HOST), err
        )
        raise ConfigEntryNotReady from err

    shc_info = session.information
    # The async information object (_AsyncSHCInformation) does not expose
    # updateState; guard so the optional update-available hint never blocks setup.
    _update_state = getattr(shc_info, "updateState", None)
    if _update_state is not None and _update_state.name == "UPDATE_AVAILABLE":
        LOGGER.warning("Please check for software updates in the Bosch Smart Home App")

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(shc_info.unique_id))},
        identifiers={(DOMAIN, shc_info.unique_id)},
        manufacturer="Bosch",
        name=entry.title,
        model="SmartHomeController",
        sw_version=shc_info.version,
    )
    device_id = device_entry.id
    entry.runtime_data = SHCData(
        session=session,
        shc_device=device_entry,
        title=entry.title,
    )
    # Keep hass.data[DOMAIN] populated so legacy code paths (device_trigger,
    # diagnostics) that still read hass.data work during the transition.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_SESSION: session,
        DATA_SHC: device_entry,
        DATA_TITLE: entry.title,
    }

    # Daily certificate re-check scheduling
    async def _scheduled_cert_check(_now):
        # async_track_time_interval dispatches sync callbacks to a worker
        # thread, where hass.async_create_task triggers HA 2026.x's escalated
        # report_non_thread_safe_operation RuntimeError for custom integrations.
        # Making the callback async makes async_track_time_interval schedule it
        # directly on the event loop, eliminating both the wrapper and the bug.
        if not cert_path:
            return  # no cert configured — nothing to check (mirrors startup guard)
        try:
            info = await hass.async_add_executor_job(parse_certificate, cert_path)
        except Exception:  # silently ignore parsing issues
            return
        if info.days_remaining < 0:
            LOGGER.error(
                "Bosch SHC client certificate expired on %s (daily check). Triggering reload for re-auth.",
                info.not_after.date(),
            )
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
        elif info.days_remaining <= CERT_EXPIRY_WARNING_DAYS:
            expiry = info.not_after.date()
            pn_async_create(
                hass,
                (
                    f"Bosch SHC client certificate will expire in {info.days_remaining} days (on {expiry}).\n"
                    "To renew: Put the controller into pairing mode and re-authenticate the integration."
                ),
                title="Bosch SHC certificate expiring",
                notification_id=DOMAIN_NOTIFICATION_ID,
            )

    entry.runtime_data.cert_check_unsub = async_track_time_interval(
        hass, _scheduled_cert_check, timedelta(days=1)
    )
    hass.data[DOMAIN][entry.entry_id][DATA_CERT_CHECK_UNSUB] = (
        entry.runtime_data.cert_check_unsub
    )

    # Presence-based child lock: optional; zero overhead when unconfigured.
    # Backward compat: stored value may be a str (old single-select) or a list.
    _raw_presence = entry.options.get(OPT_PRESENCE_ENTITY, [])
    if isinstance(_raw_presence, str):
        presence_entities = [_raw_presence] if _raw_presence else []
    else:
        presence_entities = [e for e in _raw_presence if e]

    # Master on/off switch. Defaults to ON when presence entities are already
    # configured (preserves behaviour for setups made before the toggle existed).
    child_lock_enabled = entry.options.get(
        OPT_CHILD_LOCK_ENABLED, bool(presence_entities)
    )

    if child_lock_enabled and presence_entities:
        # "Present" is auto-inferred per entity domain — no config knob needed:
        #   person / device_tracker / group  -> state == "home"
        #   zone                             -> occupancy count > 0
        #   binary_sensor / input_boolean    -> state == "on"
        def _entity_is_present(entity_id, state_obj) -> bool:
            domain = entity_id.split(".", 1)[0]
            value = state_obj.state
            if domain == "zone":
                try:
                    return int(value) > 0
                except (TypeError, ValueError):
                    return False
            if domain in ("binary_sensor", "input_boolean"):
                return value == "on"
            # person, device_tracker, group and anything else use the standard
            # home/away semantics (group of presence entities reports "home").
            return value in ("home", "on")

        # Track last-applied lock state to suppress redundant API writes.
        _last_lock_state: list[bool | None] = [None]

        def _child_lock_devices(session):
            """Return (thermostat_devices, bool_devices) from this SHC session."""
            dh = session.device_helper
            thermostats = (
                dh.thermostats
                + dh.roomthermostats
                + [d for d in dh.wallthermostats if hasattr(d, "child_lock")]
            )
            bool_devices = (
                dh.micromodule_shutter_controls
                + dh.micromodule_blinds
                + dh.micromodule_light_attached
                + dh.micromodule_relays
                + dh.micromodule_impulse_relays
                + dh.micromodule_dimmers
                + dh.light_switches_bsm
            )
            return thermostats, bool_devices

        async def _apply_child_lock(lock_state: bool):
            """Set child lock on all SHC devices (async; on the event loop)."""
            import asyncio
            import aiohttp
            from boschshcpy.exceptions import SHCException, SHCConnectionError
            from boschshcpy.api import JSONRPCError
            thermostats, bool_devices = _child_lock_devices(session)
            for device in thermostats + bool_devices:
                try:
                    await device.async_set_child_lock(lock_state)
                except (
                    JSONRPCError,
                    SHCException,
                    SHCConnectionError,
                    AttributeError,
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                ) as err:
                    LOGGER.warning(
                        "Failed to set child_lock=%s on %s: %s",
                        lock_state, device.id, err,
                    )

        @callback
        def _presence_state_changed(event):
            """Handle state changes for any tracked presence entity.

            Semantics: child lock ON when ANY tracked entity is present;
            OFF when ALL are away. "Present" is auto-inferred per domain.
            Redundant writes are suppressed via _last_lock_state.
            """
            new_state = event.data.get("new_state")
            if new_state is None:
                return
            # Skip unavailable/unknown — entity is in a transient state.
            if new_state.state in ("unavailable", "unknown"):
                return

            # Recompute aggregate: is ANY tracked entity present?
            any_present = False
            for eid in presence_entities:
                state_obj = hass.states.get(eid)
                if state_obj is None:
                    continue
                if _entity_is_present(eid, state_obj):
                    any_present = True
                    break

            lock_on = any_present
            # Suppress redundant API writes.
            if lock_on == _last_lock_state[0]:
                return
            _last_lock_state[0] = lock_on
            hass.async_create_task(_apply_child_lock(lock_on))

        entry.runtime_data.presence_unsub = async_track_state_change_event(
            hass, presence_entities, _presence_state_changed
        )

    # Presence + time-window driven silent mode: optional, default off.
    # When enabled and someone is present AND the current time is inside the
    # configured window, MODE_SILENT is set on every silent-mode-capable device;
    # otherwise MODE_NORMAL. Mirrors the child-lock feature but adds a window.
    silent_mode_enabled = entry.options.get(OPT_SILENT_MODE_ENABLED, False)

    def _parse_time(value):
        """Parse an 'HH:MM[:SS]' option value into a datetime.time, or None."""
        if not value:
            return None
        try:
            parts = str(value).split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            second = int(parts[2]) if len(parts) > 2 else 0
            return dt_time(hour, minute, second)
        except (ValueError, IndexError):
            return None

    silent_start = _parse_time(entry.options.get(OPT_SILENT_MODE_START))
    silent_end = _parse_time(entry.options.get(OPT_SILENT_MODE_END))

    if silent_mode_enabled and presence_entities and silent_start and silent_end:

        def _silent_entity_is_present(entity_id) -> bool:
            state_obj = hass.states.get(entity_id)
            if state_obj is None or state_obj.state in ("unavailable", "unknown"):
                return False
            domain = entity_id.split(".", 1)[0]
            value = state_obj.state
            if domain == "zone":
                try:
                    return int(value) > 0
                except (TypeError, ValueError):
                    return False
            if domain in ("binary_sensor", "input_boolean"):
                return value == "on"
            return value in ("home", "on")

        def _within_window() -> bool:
            now_t = dt_util.now().time()
            if silent_start == silent_end:
                return False
            if silent_start < silent_end:
                return silent_start <= now_t < silent_end
            # Overnight window (e.g. 22:00 → 06:00).
            return now_t >= silent_start or now_t < silent_end

        _last_silent_state: list[bool | None] = [None]

        async def _apply_silent(silent_on: bool):
            """Set silent mode on all capable SHC devices (async; on the loop)."""
            import asyncio
            import aiohttp
            from boschshcpy.exceptions import SHCException, SHCConnectionError
            from boschshcpy.api import JSONRPCError
            dh = session.device_helper
            devices = [
                d
                for d in (dh.thermostats + dh.roomthermostats)
                if getattr(d, "supports_silentmode", False)
            ]
            for device in devices:
                try:
                    await device.async_set_silentmode(silent_on)
                except (
                    JSONRPCError,
                    SHCException,
                    SHCConnectionError,
                    AttributeError,
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                ) as err:
                    LOGGER.warning(
                        "Failed to set silent_mode=%s on %s: %s",
                        silent_on, device.id, err,
                    )

        @callback
        def _evaluate_silent(*_args):
            """Recompute desired silent state and apply when it changed."""
            any_present = any(
                _silent_entity_is_present(eid) for eid in presence_entities
            )
            silent_on = any_present and _within_window()
            if silent_on == _last_silent_state[0]:
                return
            _last_silent_state[0] = silent_on
            hass.async_create_task(_apply_silent(silent_on))

        # Re-evaluate on presence change and at the two window boundaries.
        entry.runtime_data.silent_mode_unsubs.append(
            async_track_state_change_event(
                hass, presence_entities, _evaluate_silent
            )
        )
        entry.runtime_data.silent_mode_unsubs.append(
            async_track_time_change(
                hass,
                _evaluate_silent,
                hour=silent_start.hour,
                minute=silent_start.minute,
                second=silent_start.second,
            )
        )
        entry.runtime_data.silent_mode_unsubs.append(
            async_track_time_change(
                hass,
                _evaluate_silent,
                hour=silent_end.hour,
                minute=silent_end.minute,
                second=silent_end.second,
            )
        )
        # Apply the correct state once at startup.
        _evaluate_silent()

    async def stop_polling(event):
        """Stop polling service."""
        LOGGER.debug(
            "Bosch SHC '%s': stopping long-poll session (HA shutdown).", entry.title
        )
        await session.stop_polling()

    LOGGER.debug(
        "Bosch SHC '%s': starting long-poll session (local_push).", entry.title
    )
    # Async long-poll: start_polling() creates an asyncio.Task on the loop
    # (no thread, no executor). Callbacks fire on the event loop directly.
    await session.start_polling()
    LOGGER.info("Bosch SHC '%s' connected and polling.", entry.title)
    entry.runtime_data.polling_handler = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, stop_polling
    )
    hass.data[DOMAIN][entry.entry_id][DATA_POLLING_HANDLER] = (
        entry.runtime_data.polling_handler
    )

    @callback
    def _scenario_trigger(event_data):
        # Fired from the async poll loop — already on the event loop, so fire
        # directly (no call_soon_threadsafe marshalling).
        hass.bus.async_fire(
            EVENT_BOSCH_SHC,
            {
                ATTR_DEVICE_ID: device_id,
                ATTR_ID: event_data["id"],
                ATTR_NAME: shc_info.name,
                ATTR_LAST_TIME_TRIGGERED: event_data["lastTimeTriggered"],
                ATTR_EVENT_TYPE: "SCENARIO",
                ATTR_EVENT_SUBTYPE: event_data["name"],
            },
        )

    session.subscribe_scenario_callback("shc", _scenario_trigger)

    for switch_device in session.device_helper.universal_switches:
        event_listener = SwitchDeviceEventListener(hass, entry, switch_device)
        await event_listener.async_setup()

    # Register rawscan diagnostic service when the option is enabled (default: on).
    # The service is domain-scoped but opt-in: only register when at least one
    # entry enables it; unregister when the last enabling entry is unloaded.
    if entry.options.get(OPT_ENABLE_RAWSCAN, True):
        _register_rawscan_service(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    runtime: SHCData = entry.runtime_data
    runtime.session.unsubscribe_scenario_callback("shc")

    if runtime.polling_handler is not None:
        runtime.polling_handler()
    if runtime.cert_check_unsub is not None:
        runtime.cert_check_unsub()
    if runtime.presence_unsub is not None:
        runtime.presence_unsub()
    for _unsub in runtime.silent_mode_unsubs:
        _unsub()
    runtime.silent_mode_unsubs.clear()
    await runtime.session.stop_polling()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    # Remove rawscan service if no remaining loaded entries have it enabled.
    if hass.services.has_service(DOMAIN, SERVICE_TRIGGER_RAWSCAN):
        remaining = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
            and e.state is ConfigEntryState.LOADED
            and e.options.get(OPT_ENABLE_RAWSCAN, True)
        ]
        if not remaining:
            hass.services.async_remove(DOMAIN, SERVICE_TRIGGER_RAWSCAN)

    return unload_ok


class SwitchDeviceEventListener:
    """Event listener for a Switch device."""

    def __init__(self, hass, entry, device: SHCUniversalSwitch):
        """Initialize the Switch device event listener."""
        self.hass = hass
        self.entry = entry
        self._device = device
        self._keypad_service = None
        self.device_id = None

        for service in self._device.device_services:
            if service.id == "Keypad":
                self._keypad_service = service
                break

        # Store the unsub callable so it can be cancelled on unload/shutdown,
        # preventing a stale listener from leaking across reloads.
        self._ha_stop_unsub = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop
        )

    def _input_events_handler(self):
        """Handle device input events (fired on the event loop by the async session)."""
        if self._device.eventtype is None:
            return
        event_type = self._device.eventtype.name

        if event_type in SUPPORTED_INPUTS_EVENTS_TYPES:
            # The async session fires callbacks on the event loop, so fire the
            # bus event directly (no call_soon_threadsafe marshalling).
            self.hass.bus.async_fire(
                EVENT_BOSCH_SHC,
                {
                    ATTR_DEVICE_ID: self.device_id,
                    ATTR_ID: self._device.id,
                    ATTR_NAME: self._device.name,
                    ATTR_LAST_TIME_TRIGGERED: self._device.eventtimestamp,
                    ATTR_EVENT_SUBTYPE: self._device.keyname.name,
                    ATTR_EVENT_TYPE: event_type,
                },
            )
        else:
            LOGGER.warning(
                "Switch input event %s for device %s is not supported, please open issue",
                event_type,
                self._device.name,
            )

    async def async_setup(self):
        """Set up the listener."""
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            name=self._device.name,
            identifiers={(DOMAIN, self._device.id)},
            manufacturer=self._device.manufacturer,
            model=self._device.device_model,
            via_device=(DOMAIN, self._device.root_device_id),
        )
        self.device_id = device_entry.id
        if self._keypad_service is not None:
            self._keypad_service.subscribe_callback(
                self._device.id, self._input_events_handler
            )

    def shutdown(self):
        """Shutdown the listener."""
        # Cancel the HA-stop listener to prevent leaks across reloads.
        if self._ha_stop_unsub is not None:
            self._ha_stop_unsub()
            self._ha_stop_unsub = None
        self._keypad_service.unsubscribe_callback(self._device.id)

    @callback
    def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        LOGGER.debug("Stopping Switch event listener for %s", self._device.name)
        self.shutdown()
