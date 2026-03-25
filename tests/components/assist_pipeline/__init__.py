"""Tests for the Voice Assistant integration."""

from dataclasses import asdict
from unittest.mock import ANY

from homeassistant.components import assist_pipeline

MANY_LANGUAGES = [
    "ar",
    "bg",
    "bn",
    "ca",
    "cs",
    "da",
    "de",
    "de-CH",
    "el",
    "en",
    "es",
    "fa",
    "fi",
    "fr",
    "fr-CA",
    "gl",
    "gu",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "is",
    "it",
    "ka",
    "kn",
    "lb",
    "lt",
    "lv",
    "ml",
    "mn",
    "ms",
    "nb",
    "nl",
    "pl",
    "pt",
    "pt-br",
    "ro",
    "ru",
    "sk",
    "sl",
    "sr",
    "sv",
    "sw",
    "te",  # codespell:ignore te
    "tr",
    "uk",
    "ur",
    "vi",
    "zh-cn",
    "zh-hk",
    "zh-tw",
]


def process_events(events: list[assist_pipeline.PipelineEvent]) -> list[dict]:
    """Process events to remove dynamic values."""
    processed = []
    for event in events:
        as_dict = asdict(event)
        as_dict.pop("timestamp")
        if as_dict["type"] == assist_pipeline.PipelineEventType.RUN_START:
            as_dict["data"]["pipeline"] = ANY
        processed.append(as_dict)

    return processed
