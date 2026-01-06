"""Tests for the OctoPrint integration."""

from __future__ import annotations

DEFAULT_JOB = {
    "job": {
        "averagePrintTime": None,
        "estimatedPrintTime": None,
        "filament": None,
        "file": {
            "date": None,
            "display": None,
            "name": None,
            "origin": None,
            "path": None,
            "size": None,
        },
        "lastPrintTime": None,
        "user": None,
    },
    "progress": {"completion": 50},
}

DEFAULT_PRINTER = {
    "state": {
        "flags": {"printing": True, "error": False},
        "text": "Operational",
    },
    "temperature": [],
}
