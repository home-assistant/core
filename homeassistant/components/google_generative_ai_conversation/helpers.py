"""Helper classes for Google Generative AI integration."""

from contextlib import suppress
from dataclasses import dataclass
from functools import cache
import importlib
import io
import pkgutil
import sys
from typing import Any, Literal
import wave

from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER


@cache
def _warmup_gaos_once() -> None:
    """Pre-populate google.genai._gaos dynamic imports in executor once."""
    with suppress(Exception):
        import google.genai._gaos  # noqa: PLC0415
        import google.genai._gaos.utils.dynamic_imports as di  # noqa: PLC0415

        orig_lazy_getattr = di.lazy_getattr

        def _caching_lazy_getattr(
            attr_name: str,
            *,
            package: str,
            dynamic_imports: dict[str, str],
            sub_packages: list[str] | None = None,
        ) -> Any:
            val = orig_lazy_getattr(
                attr_name,
                package=package,
                dynamic_imports=dynamic_imports,
                sub_packages=sub_packages,
            )
            if package in sys.modules:
                setattr(sys.modules[package], attr_name, val)
            return val

        di.lazy_getattr = _caching_lazy_getattr

        for _, name, _ in pkgutil.walk_packages(
            google.genai._gaos.__path__,  # noqa: SLF001
            google.genai._gaos.__name__ + ".",  # noqa: SLF001
        ):
            with suppress(Exception):
                mod = importlib.import_module(name)
                if hasattr(mod, "_dynamic_imports"):
                    for attr in list(mod._dynamic_imports.keys()):  # noqa: SLF001
                        setattr(mod, attr, getattr(mod, attr))
                if hasattr(mod, "_sub_packages") and mod._sub_packages:  # noqa: SLF001
                    for subpkg in mod._sub_packages:  # noqa: SLF001
                        setattr(mod, subpkg, getattr(mod, subpkg))


def warmup_gaos(client: Any = None) -> None:
    """Pre-populate google.genai._gaos dynamic imports in executor to prevent blocking import_module in event loop."""
    _warmup_gaos_once()

    if client is not None:
        with suppress(Exception):
            _ = client.aio.interactions


@dataclass(slots=True)
class PartDetails:
    """Additional data for a content part."""

    part_type: Literal[
        "text", "thought", "function_call", "google_search_call", "google_search_result"
    ]
    """The part type for which this data is relevant for."""

    index: int
    """Start position or number of the tool."""

    length: int = 0
    """Length of the relevant data."""

    thought_signature: str | None = None
    """Signature, if available."""

    search_result: Any = None
    """Google Search result data, if available."""


@dataclass(slots=True)
class ContentDetails:
    """Native data for AssistantContent."""

    part_details: list[PartDetails]


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Generate a WAV file header for the given audio data and parameters.

    Args:
        audio_data: The raw audio data as a bytes object.
        mime_type: Mime type of the audio data.

    Returns:
        A bytes object representing the WAV file header.

    """
    if mime_type.lower().startswith(
        ("audio/wav", "audio/x-wav")
    ) or audio_data.startswith(b"RIFF"):
        return audio_data

    parameters = _parse_audio_mime_type(mime_type)

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(parameters["bits_per_sample"] // 8)
        wf.setframerate(parameters["rate"])
        wf.writeframes(audio_data)

    return wav_buffer.getvalue()


# Below code is from https://aistudio.google.com/app/generate-speech
# when you select "Get SDK code to generate speech".
def _parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    """Parse bits per sample and rate from an audio MIME type string.

    Assumes bits per sample is encoded like "L16" and rate as "rate=xxxxx".

    Args:
        mime_type: The audio MIME type string (e.g., "audio/L16;rate=24000").

    Returns:
        A dictionary with "bits_per_sample" and "rate" keys. Values will be
        integers if found, otherwise None.

    """
    if mime_type.lower().startswith(("audio/wav", "audio/x-wav")):
        return {"bits_per_sample": 16, "rate": 24000}

    if not mime_type.lower().startswith("audio/l"):
        LOGGER.warning("Received unexpected MIME type %s", mime_type)
        raise HomeAssistantError(f"Unsupported audio MIME type: {mime_type}")

    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts:  # Skip the main type part
        param = param.strip()
        if param.lower().startswith("rate="):
            # Handle cases like "rate=" with no value or
            # non-integer value and keep rate as default
            with suppress(ValueError, IndexError):
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
        elif param.lower().startswith("audio/l"):
            # Keep bits_per_sample as default if conversion fails
            with suppress(ValueError, IndexError):
                bits_per_sample = int(param.upper().split("L", 1)[1])

    return {"bits_per_sample": bits_per_sample, "rate": rate}
