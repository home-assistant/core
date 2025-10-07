#!/usr/bin/env python3
"""Dump OpenRGB data in JSON format to stdout.

This script connects to an OpenRGB SDK server and dumps all device data
in JSON format. It's useful for debugging, testing, and understanding the
structure of OpenRGB devices.

Usage:
    # Connect to 127.0.0.1:6742 (default)
    python dump_openrgb_data.py

    # Connect to 192.168.1.100:6742
    python dump_openrgb_data.py 192.168.1.100

    # Connect to 192.168.1.100:8080
    python dump_openrgb_data.py 192.168.1.100 8080

    # Save output to a file
    python dump_openrgb_data.py 192.168.1.100 > openrgb_data.json
"""

from enum import Enum
import json
import os
import sys
from typing import Any

from openrgb import OpenRGBClient


def serialize_obj(obj: Any) -> object:
    """Convert objects to JSON-serializable format."""
    if isinstance(obj, Enum):
        # Include Enum class information for reconstruction
        enum_class = obj.__class__
        return {
            "__enum__": f"{enum_class.__module__}.{enum_class.__qualname__}",
            "name": obj.name,
            "value": obj.value,
        }
    if isinstance(obj, list):
        return [serialize_obj(item) for item in obj]
    if isinstance(obj, dict):
        return {k: serialize_obj(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        result = {}

        # Include regular attributes
        for k, v in vars(obj).items():
            # Exclude useless data
            if k not in ("comms", "data", "_colors"):
                result[k] = serialize_obj(v)

        # Include @property attributes
        for attr_name in dir(obj):
            if isinstance(getattr(type(obj), attr_name, None), property):
                result[attr_name] = serialize_obj(getattr(obj, attr_name))

        return result
    return obj


# Parse address and port from command line or use defaults
address = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.15"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 6742

# Connect to OpenRGB
client = OpenRGBClient(address=address, port=port, name=os.path.basename(__file__))

# Output JSON to stdout
print(json.dumps(serialize_obj(client), indent=2, sort_keys=True))  # noqa: T201
