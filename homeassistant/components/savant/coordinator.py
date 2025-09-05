"""Provides DataUpdateCoordinator."""

from datetime import timedelta
import logging
import typing

from pysavant.switch import AudioSwitch, Switch, VideoSwitch

from homeassistant.components.button import ButtonEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .media_player import SavantPlayer

logger = logging.getLogger(__name__)


class SavantCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator for Savant matrix switch."""

    players: list[SavantPlayer] = []
    sensors: list[SensorEntity] = []
    buttons: list[ButtonEntity] = []
    info: dict[str, typing.Any]
    api: Switch | None = None

    def __init__(self, hass, entry):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            logger,
            name=entry.data["name"],
            config_entry=entry,
            update_interval=timedelta(seconds=1),
            always_update=True,
        )
        match entry.data["type"]:
            case "Audio":
                self.api = AudioSwitch(entry.data["ip"])
            case "Video":
                self.api = VideoSwitch(entry.data["ip"])
            case _:
                raise ConfigEntryError
        self.inputs = self.config_entry.data["inputs"]
        self.input_ids = {v: k for k, v in self.inputs.items()}
        self.outputs = self.config_entry.data["outputs"]
        self.output_ids = {v: k for k, v in self.outputs.items()}
        logger.debug(
            "created savant coordinator for %s with config %s",
            entry.data["name"],
            entry,
        )

    async def _async_setup(self):
        info = await self.api.get_info()
        logger.debug("coordinator has info %s", info)
        self.info = info

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        data = await self.api.get_switch_state()

        def make_port_data(data):
            data["port"]
            state = "IDLE" if data["inputsrc"] == 0 else "PLAYING"
            source_port = None if state == "IDLE" else str(data["inputsrc"])
            if source_port is None:
                source = None
            else:
                source = self.inputs.get(source_port, source_port)
            return {"state": state, "source": source, "other": data}

        return {port["port"]: make_port_data(port) for port in data["outputs"]}


class SavantAudioSwitchCoordinator(SavantCoordinator):
    """Provides additional coordinator functionality needed for audio matrices."""


class SavantVideoSwitchCoordinator(SavantCoordinator):
    """Provides additional coordinator functionality needed for video matrices."""
