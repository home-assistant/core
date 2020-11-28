"""The PulseAudio integration."""
import asyncio
from queue import Empty, Queue
from threading import Event, Thread

from pulsectl import Pulse, PulseError, PulseVolumeInfo, _pulsectl
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_SERVER, DOMAIN

UNDO_UPDATE_LISTENER = "undo_update_listener"
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["media_player"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the PulseAudio component."""
    return True


class PulseAudioInterface:
    """Interface to PulseAudio.

    Handles all interactions with server from a single thread.
    """

    _queue: Queue = Queue()
    _connected: bool = False
    _sink_list = None
    _source_list = None
    _module_list = None

    def __init__(self, hass, server: str):
        """Initialize."""

        def pulse_thread(cmd_queue: Queue, server: str):
            pulse = Pulse(server=server)
            while True:
                try:
                    try:
                        (func, ev) = cmd_queue.get(block=True, timeout=2)

                        if (func, ev) == (None, None):
                            return

                        func(pulse)
                        ev.set()

                    except Empty:
                        pass

                    self._connected = pulse.connected
                    if not self._connected:
                        pulse.connect()

                    self._module_list = pulse.module_list()
                    self._sink_list = pulse.sink_list()
                    self._source_list = pulse.source_list()

                except (PulseError, _pulsectl.LibPulse.CallError):
                    self._connected = False
                    pulse.disconnect()

        self.hass = hass

        self._thread = Thread(
            target=pulse_thread, name="PulseAudio_" + server, args=(self._queue, server)
        )

        self._thread.start()

    def stop(self):
        """Stop the PulseAudio thread."""
        self._queue.put((None, None))
        self._thread.join()

    async def _async_pulse_call(self, func):
        """Execute function in the context of the PulseAudio thread."""
        ev = Event()
        self._queue.put((func, ev))
        await self.hass.async_add_executor_job(ev.wait)

    async def async_sink_volume_set(self, sink, volume: float):
        """Set volume for sink."""
        await self._async_pulse_call(
            lambda pulse, sink=sink, volume=volume: pulse.sink_volume_set(
                sink.index, PulseVolumeInfo(volume, len(sink.volume.values))
            )
        )

    async def async_sink_mute(self, sink, mute):
        """Mute sink."""
        await self._async_pulse_call(
            lambda pulse, index=sink.index, mute=mute: pulse.sink_mute(index, mute)
        )

    def _get_module_idx(self, sink_name, source_name):
        """Get index of loopback module from source to sink."""
        for module in self._module_list:
            if not module.name == "module-loopback":
                continue

            if f"sink={sink_name}" not in module.argument:
                continue

            if f"source={source_name}" not in module.argument:
                continue

            return module.index

        return None

    async def async_connect_source(self, sink, source_name, sources):
        """Connect a source to a sink."""
        for source in sources:
            idx = self._get_module_idx(sink.name, source)
            if source == source_name:
                if not idx:
                    await self._async_pulse_call(
                        lambda pulse, sink=sink.name, source=source: pulse.module_load(
                            "module-loopback", args=f"sink={sink} source={source}"
                        )
                    )
            else:
                if not idx:
                    continue

                await self._async_pulse_call(
                    lambda pulse, idx=idx: pulse.module_unload(idx)
                )

    def get_connected_source(self, sink, sources):
        """Get source that is connected to sink."""
        if sink:
            for source in sources:
                idx = self._get_module_idx(sink.name, source)
                if idx:
                    return source
        return None

    def get_sink_by_name(self, name):
        """Get PulseAudio sink by name."""
        if not self._sink_list:
            return None

        return [s for s in self._sink_list if s.name == name][0]

    @property
    def connected(self):
        """Return true when connected to server."""
        return self._connected


interfaces = {}


def get_pulse_interface(hass, server: str) -> PulseAudioInterface:
    """Get interface to server."""
    if server not in interfaces:
        interfaces[server] = PulseAudioInterface(hass, server)
    return interfaces[server]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the PulseAudio components from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    server = entry.data[CONF_SERVER]

    undo_listener = entry.add_update_listener(async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_SERVER: server,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()

    entity_registry = await er.async_get_registry(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    for entry in entries:
        entity_registry.async_remove(entry.entity_id)

    if unload_ok:
        data = hass.data[DOMAIN].pop(config_entry.entry_id)
        if data[CONF_SERVER] in interfaces:
            interfaces.pop(data[CONF_SERVER]).stop()

    return unload_ok


async def async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
