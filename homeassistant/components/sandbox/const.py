"""Constants for the Sandbox v2 integration."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import SandboxV2Data

DOMAIN = "sandbox_v2"

DATA_SANDBOX_V2: HassKey[SandboxV2Data] = HassKey(DOMAIN)

# Proxy entities all register under the shared ``sandbox_v2`` platform_name,
# so the entity-registry uniqueness key ``(domain, "sandbox_v2", unique_id)``
# would collide when two integrations in one group reuse a unique_id. The
# proxy unique_id is therefore namespaced as
# ``f"{source_domain}{UNIQUE_ID_SEPARATOR}{unique_id}"``. ``:`` is chosen
# because HA's default slug logic never produces it, so it cannot clash with
# a real unique_id segment.
UNIQUE_ID_SEPARATOR = ":"

# Platforms that the sandbox cannot host today. Any integration that ships a
# platform file in this set is forced onto `main`. Each entry needs a one-line
# "why" so the deny-list is reviewable.
#
# TODO(sandbox_v2): revisit each entry once the protocol can carry the missing
# payload shape. Tracked in sandbox_v2/plan.md "Risks → Deny-list rot".
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
    }
)

# Integrations that must always run on main, regardless of platform shape.
ALWAYS_MAIN: frozenset[str] = frozenset(
    {
        "script",
        "automation",
        "scene",
        "cloud",
        # ai_task's service handler resolves attachments into Attachment
        # objects with Path values + temp files before the entity method
        # runs. Neither bridge option intercepts at service-call level yet,
        # and resolution depends on camera/image bytes (deny-listed). Folded
        # in the Phase 1 decision doc — revisit when ai_task is made
        # sandbox-aware or we add service-handler-level interception.
        "ai_task",
        # image owns the same bytes-returning entity surface camera does;
        # the deny-list above catches integrations *providing* an image
        # platform, but the image integration itself needs to stay on main
        # so consumers (ai_task, etc.) can fetch bytes locally.
        "image",
        # Broad readers — read ALL entities / registries, not narrowly
        # scopable, so they break under sandbox lockdown. See
        # sandbox_v2/plans/research/builtin-lockdown-breakage.md (point 1,
        # decision: blanket ALWAYS_MAIN).
        # template: Jinja states()/is_state() over any entity at render time.
        "template",
        # group: state/attrs derive entirely from foreign member entities.
        "group",
        # homekit: hass.states.async_all() + entity/device registries.
        "homekit",
        # Source-entity helpers — read a declared set of foreign entities
        # (and sometimes the registries). ALWAYS_MAIN until the share-states
        # consumer lands a scoped declared-source-entity allow-list.
        # min_max: min/max/mean over foreign sensors.
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
