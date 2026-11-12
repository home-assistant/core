"""Constants for the Sandbox integration."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import SandboxData

DOMAIN = "sandbox"

DATA_SANDBOX: HassKey[SandboxData] = HassKey(DOMAIN)

# Namespace IDs because integrations share the sandbox platform registry key.
UNIQUE_ID_SEPARATOR = ":"

# Keep platforms on main when the protocol cannot carry their data.
SANDBOX_INCOMPATIBLE_PLATFORMS: frozenset[str] = frozenset(
    {
        # stt: streams audio chunks via async generator; not serializable over WS.
        "stt",
        # tts: returns audio bytes + streaming variants the bridge has no path for.
        "tts",
        # conversation: agent API exchanges live chat objects and tool callbacks.
        "conversation",
        # assist_satellite: bidirectional audio pipeline + wake/voice runtime state.
        "assist_satellite",
        # wake_word: streaming detector entities yielding bytes/audio chunks.
        "wake_word",
        # camera: entity surface returns image/stream bytes; needs a byte channel.
        "camera",
        # The synchronous todo_items property needs a pushed cache, not query RPCs.
        "todo",
    }
)

# Integrations that must always run on main, regardless of platform shape.
ALWAYS_MAIN: frozenset[str] = frozenset(
    {
        "script",
        "automation",
        "scene",
        "cloud",
        # Attachment paths and temporary files must be resolved on main.
        "ai_task",
        # Keep image providers on main for consumers that read image bytes locally.
        "image",
        # These integrations need access to states or registries outside their group.
        "template",
        # group: state/attrs derive entirely from foreign member entities.
        "group",
        # homekit: hass.states.async_all() + entity/device registries.
        "homekit",
        # These helpers need foreign states that the bridge does not subscribe to.
        "min_max",
        # statistics: stats buffer over a foreign entity.
        "statistics",
        # trend: gradient of a foreign sensor.
        "trend",
        # threshold: compares a foreign sensor to bounds.
        "threshold",
        # derivative: time-derivative of a foreign sensor.
        "derivative",
        # integration: Riemann integral of a foreign sensor.
        "integration",
        # utility_meter: tracks a foreign energy sensor.
        "utility_meter",
        # filter: filtered passthrough of a foreign sensor.
        "filter",
        # mold_indicator: computes from foreign temp + humidity sensors.
        "mold_indicator",
        # bayesian: probability from many foreign states.
        "bayesian",
        # generic_thermostat: reads a foreign sensor, drives a foreign switch.
        "generic_thermostat",
        # generic_hygrostat: same as generic_thermostat for humidity.
        "generic_hygrostat",
        # switch_as_x: mirrors a foreign switch; also reads the registry.
        "switch_as_x",
        # history_stats: needs foreign state + recorder history.
        "history_stats",
        # proximity: distance of foreign trackers to a foreign zone.
        "proximity",
    }
)
