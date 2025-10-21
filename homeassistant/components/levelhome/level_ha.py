"""Local import seam that re-exports library-style API.

This allows later switching to an external package by changing imports here.
"""

from __future__ import annotations

from aiohttp import ClientSession  # re-exported for type checkers in consumers

from .api import ApiError, Client  # re-export
from .ws import LevelWebsocketManager as WebsocketManager  # re-export

__all__ = [
    "ApiError",
    "Client",
    "WebsocketManager",
    "ClientSession",
]


