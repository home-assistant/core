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

    # Save output to data.json
    python dump_openrgb_data.py 192.168.1.100 > data.json
"""

import os
import sys

import jsonpickle
from jsonpickle import handlers
from openrgb import OpenRGBClient
from openrgb.network import NetworkClient


class NetworkClientHandler(handlers.BaseHandler):
    """Handler to exclude NetworkClient objects from serialization."""

    def flatten(self, obj, data):
        """Return None to exclude NetworkClient from output."""
        return


# Register the handler to exclude NetworkClient objects
handlers.register(NetworkClient, NetworkClientHandler)

# Configure encoder to sort keys
jsonpickle.set_encoder_options("json", sort_keys=True)

# Parse address and port from command line or use defaults
address = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 6742

# Connect to OpenRGB
client = OpenRGBClient(address=address, port=port, name=os.path.basename(__file__))

# Print the JSON to stdout
print(jsonpickle.encode(client, make_refs=False, indent=2))  # noqa: T201
