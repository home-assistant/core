"""Model-family capabilities for Azure OpenAI request shaping."""

from dataclasses import dataclass
import re
from typing import Literal, cast

type ReasoningEffort = Literal[
    "none", "minimal", "low", "medium", "high", "xhigh", "max"
]


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities declared for an underlying model, never a deployment name."""

    features: frozenset[str] = frozenset({"sampling"})
    reasoning: tuple[ReasoningEffort, ...] = ()
    summaries: tuple[str, ...] = ()

    @property
    def reasoning_summary(self) -> list[str]:
        """Return supported reasoning summaries."""
        return ["off", *self.summaries] if self.summaries else []

    def reasoning_effort(self, effort: str) -> ReasoningEffort:
        """Choose a supported effort, including for recommended settings."""
        for supported in self.reasoning:
            if effort == supported:
                return supported
        return "low" if "low" in self.reasoning else self.reasoning[0]

    def supports_sampling(self, effort: str | None = None) -> bool:
        """Return whether temperature and top_p are supported."""
        return "sampling" in self.features or (
            "sampling_none" in self.features and effort == "none"
        )


# Microsoft Learn: /azure/foundry/openai/how-to/{responses,reasoning,prompt-caching}
# Dated snapshots inherit only their exact family; custom families stay conservative.
# Azure documents Responses model availability but no per-model hosted-tool matrix,
# so "code" and "image" follow the per-model "Tools supported by this model when
# using the Responses API" lists at developers.openai.com/api/docs/models/<id>.
# Support is per model, not per tier: gpt-5.5-pro lists code interpreter while the
# other Pro models do not, so never infer a family's tools from its name.
_MODEL_PROFILES = (
    ("gpt-4.1-mini", "", "", "sampling web code"),
    ("gpt-4o-mini gpt-4o", "", "", "sampling web code image"),
    ("gpt-4.1", "", "", "sampling web cache24 code image"),
    ("gpt-chat-latest gpt-4.1-nano", "", "", "sampling code image"),
    ("o3-mini", "low medium high", "", "code image"),
    ("o1", "low medium high", "", ""),
    ("o4-mini", "low medium high", "auto detailed", "web code"),
    ("o3", "low medium high", "auto detailed", "web code image"),
    (
        "gpt-5",
        "minimal low medium high",
        "auto detailed",
        "verbosity web cache24 code image",
    ),
    (
        "gpt-5-nano",
        "minimal low medium high",
        "auto detailed",
        "verbosity web code image",
    ),
    (
        "gpt-5-mini",
        "minimal low medium high",
        "auto detailed",
        "verbosity web code",
    ),
    ("gpt-5-pro", "high", "auto detailed", "verbosity web image"),
    ("gpt-5-codex", "low medium high", "auto detailed", "verbosity web cache24"),
    (
        "gpt-5.1",
        "none low medium high",
        "auto detailed",
        "sampling_none verbosity web cache24 code image",
    ),
    (
        "gpt-5.1-codex gpt-5.1-codex-mini",
        "none low medium high",
        "auto detailed",
        "sampling_none verbosity web cache24",
    ),
    (
        "gpt-5.1-codex-max",
        "low medium high xhigh",
        "auto detailed",
        "verbosity cache24",
    ),
    (
        "gpt-5.2 gpt-5.4 gpt-5.5",
        "none low medium high xhigh",
        "auto detailed",
        "sampling_none verbosity web cache24 code image",
    ),
    (
        "gpt-5.4-nano gpt-5.4-mini",
        "none low medium high xhigh",
        "auto detailed",
        "sampling_none verbosity code image",
    ),
    (
        "gpt-5.2-codex",
        "none low medium high xhigh",
        "auto detailed",
        "sampling_none verbosity web",
    ),
    (
        "gpt-5.3-codex",
        "none low medium high xhigh",
        "auto detailed",
        "sampling_none verbosity web cache24",
    ),
    ("gpt-5.4-pro", "medium high xhigh", "auto detailed", "verbosity web image"),
    (
        "gpt-5.6-luna gpt-5.6-sol gpt-5.6-terra",
        "none low medium high xhigh max",
        "auto detailed",
        "sampling_none verbosity pro web cache30 code image",
    ),
    (
        "gpt-6-astra",
        "low medium high xhigh max",
        "auto detailed",
        "verbosity pro web cache30 code image",
    ),
    (
        "o1-mini o1-preview gpt-4o-realtime-preview gpt-4o-mini-realtime-preview "
        "o3-pro o3-deep-research computer-use-preview",
        "",
        "",
        "unsupported",
    ),
)

MODEL_CAPABILITIES = {
    family: ModelCapabilities(
        frozenset(features.split()),
        cast(tuple[ReasoningEffort, ...], tuple(reasoning.split())),
        tuple(summaries.split()),
    )
    for families, reasoning, summaries, features in _MODEL_PROFILES
    for family in families.split()
}
RECOMMENDED_MODEL_FAMILIES = [
    family
    for families, _reasoning, _summaries, features in reversed(_MODEL_PROFILES)
    if "unsupported" not in features.split()
    for family in families.split()
]
_BASIC_CAPABILITIES = ModelCapabilities()

# Azure/OpenAI base image-generation model names, newest first. These are
# distinct from chat model families: they're the value the Responses API
# image_generation tool expects in its own "model" field, never a deployment name.
IMAGE_MODEL_FAMILIES = ("gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini")
RECOMMENDED_IMAGE_MODEL = IMAGE_MODEL_FAMILIES[0]

# Azure transcription models use the classic per-deployment route:
#   /openai/deployments/{deployment}/audio/transcriptions?api-version=<dated>
STT_MODEL_FAMILIES = ("whisper", "gpt-4o-transcribe")
DEFAULT_STT_API_VERSION = "2025-03-01-preview"

_TTS_VOICE_PROFILES = (
    (
        "gpt-4o-mini-tts",
        "marin cedar alloy ash ballad coral echo fable nova onyx sage shimmer verse",
    ),
    ("tts tts-hd", "alloy ash coral echo fable onyx nova sage shimmer"),
)
TTS_MODEL_FAMILIES = tuple(
    model for models, _voices in _TTS_VOICE_PROFILES for model in models.split()
)
_TTS_VOICES_BY_MODEL = {
    model: tuple(voices.split())
    for models, voices in _TTS_VOICE_PROFILES
    for model in models.split()
}
_DEFAULT_TTS_VOICES = _TTS_VOICES_BY_MODEL["tts"]


def get_tts_voices(model: str) -> tuple[str, ...]:
    """Return supported voices in default-first order for a speech model."""
    family = re.sub(r"-(?:preview-)?\d{4}-\d{2}-\d{2}$", "", model.strip())
    return _TTS_VOICES_BY_MODEL.get(family, _DEFAULT_TTS_VOICES)


def get_capabilities(model_family: str) -> ModelCapabilities:
    """Look up a family without inferring capabilities for unknown models."""
    family = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model_family.strip())
    return MODEL_CAPABILITIES.get(family, _BASIC_CAPABILITIES)
