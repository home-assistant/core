"""A 'hub' that connects several devices."""

from __future__ import annotations

import logging

from triggercmd import client, utils

_LOGGER = logging.getLogger(__name__)


class Hub:
    """Hub for TRIGGERcmd."""

    manufacturer = "TRIGGERcmd"

    def __init__(self, token: str) -> None:
        """Init hub."""
        self._id = utils.user_id(token)
        self._token = token

        r = client.list(token)
        self.switches = []
        for item in r.json():
            trigger = item["trigger"]
            computer = item["computer"]
            self.switches.append(
                Switch(f"{computer}.{trigger}", f"{computer} | {trigger}", self)
            )

        self.online = True

    @property
    def hub_id(self) -> str:
        """ID for hub."""
        return self._id

    @property
    def token(self) -> str:
        """Token for hub."""
        return self._token


class Switch:
    """switch (device for HA) for TRIGGERcmd."""

    def __init__(self, switchid: str, name: str, hub: Hub) -> None:
        """Init switch."""
        self._id = switchid
        self.hub = hub
        self.name = name
        self.firmware_version = "1.0.0"
        self.model = "Trigger Device"

    @property
    def switch_id(self) -> str:
        """Return ID for switch."""
        return self._id
