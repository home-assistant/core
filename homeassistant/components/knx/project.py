"""Handle KNX project data."""
from __future__ import annotations

from typing import Any, Final

from xknx.dpt import DPTBase

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}/knx_project.json"


class KNXProject:
    """Manage KNX project data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize project data."""
        self.hass = hass
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self.loaded: bool = False

        self.devices: dict[str, Any] = {}
        self.group_addresses: dict[str, Any] = {}

    async def load_project(self) -> None:
        """Load project data from storage."""
        if project := await self._store.async_load():
            self.devices = project["devices"]
            self.group_addresses = project["group_addresses"]

            for _ga in self.group_addresses.values():
                if dpt := _ga.get("dpt_type"):
                    if transcoder := DPTBase.transcoder_by_dpt(
                        dpt["main"], dpt.get("sub")
                    ):
                        _ga["transcoder"] = transcoder

            self.loaded = True
