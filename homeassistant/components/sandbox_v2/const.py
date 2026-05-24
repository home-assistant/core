"""Constants for the Sandbox v2 integration."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import SandboxV2Data

DOMAIN = "sandbox_v2"

DATA_SANDBOX_V2: HassKey[SandboxV2Data] = HassKey(DOMAIN)

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
    }
)
