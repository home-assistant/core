"""Base class for SUPLA channels."""

from __future__ import annotations

import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)


class SuplaEntity(CoordinatorEntity):
    """Base class of a SUPLA Channel (an equivalent of HA's Entity)."""

    def __init__(self, config, server, coordinator):
        """Init from config, hookup[ server and coordinator."""
        super().__init__(coordinator)
        self.server_name = config["server_name"]
        self.channel_id = config["channel_id"]
        self.server = server

    @property
    def channel_data(self):
        """Return channel data taken from coordinator."""
        return self.coordinator.data.get(self.channel_id)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "supla-{}-{}".format(
            self.channel_data["iodevice"]["gUIDString"].lower(),
            self.channel_data["channelNumber"],
        )

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        return self.channel_data["caption"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.channel_data is None:
            return False
        if (state := self.channel_data.get("state")) is None:
            return False
        return state.get("connected")

    async def async_action(self, action, **add_pars):
        """Run server action.

        Actions are currently hardcoded in components.
        SUPLA's API enables autodiscovery
        """
        _LOGGER.debug(
            "Executing action %s on channel %d, params: %s",
            action,
            self.channel_data["id"],
            add_pars,
        )
        await self.server.execute_action(self.channel_data["id"], action, **add_pars)

        # Update state
        await self.coordinator.async_request_refresh()
