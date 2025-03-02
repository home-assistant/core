"""Handle KNX project data."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

from xknx import XKNX
from xknx.dpt import DPTBase
from xknx.telegram.address import DeviceAddressableType, GroupAddress, GroupAddressType
from xknxproject import XKNXProj
from xknxproject.models import (
    Device,
    DPTType,
    GroupAddress as GroupAddressModel,
    GroupAddressStyle as XknxProjectGroupAddressStyle,
    KNXProject as KNXProjectModel,
    ProjectInfo,
)

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}/knx_project.json"


@dataclass
class GroupAddressInfo:
    """Group address info for runtime usage."""

    address: str
    name: str
    description: str
    dpt_main: int | None
    dpt_sub: int | None
    transcoder: type[DPTBase] | None


def _create_group_address_info(ga_model: GroupAddressModel) -> GroupAddressInfo:
    """Convert GroupAddress dict value into GroupAddressInfo instance."""
    dpt = ga_model["dpt"]
    transcoder = DPTBase.transcoder_by_dpt(dpt["main"], dpt.get("sub")) if dpt else None
    return GroupAddressInfo(
        address=ga_model["address"],
        name=ga_model["name"],
        description=ga_model["description"],
        transcoder=transcoder,
        dpt_main=dpt["main"] if dpt else None,
        dpt_sub=dpt["sub"] if dpt else None,
    )


class KNXProject:
    """Manage KNX project data."""

    loaded: bool
    devices: dict[str, Device]
    group_addresses: dict[str, GroupAddressInfo]
    info: ProjectInfo | None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize project data."""
        self.hass = hass
        self._store = Store[KNXProjectModel](hass, STORAGE_VERSION, STORAGE_KEY)

        self.initial_state()

    def initial_state(self) -> None:
        """Set initial state for project data."""
        self.loaded = False
        self.devices = {}
        self.group_addresses = {}
        self.info = None

    async def load_project(
        self, xknx: XKNX, data: KNXProjectModel | None = None
    ) -> None:
        """Load project data from storage."""
        if project := data or await self._store.async_load():
            self.devices = project["devices"]
            self.info = project["info"]
            GroupAddress.address_format = self.get_address_format()
            xknx.group_address_dpt.clear()
            xknx_ga_dict: dict[DeviceAddressableType, DPTType] = {}

            for ga_model in project["group_addresses"].values():
                ga_info = _create_group_address_info(ga_model)
                self.group_addresses[ga_info.address] = ga_info
                if (dpt_model := ga_model.get("dpt")) is not None:
                    xknx_ga_dict[ga_model["address"]] = dpt_model

            xknx.group_address_dpt.set(xknx_ga_dict)

            _LOGGER.debug(
                "Loaded KNX project data with %s group addresses from storage",
                len(self.group_addresses),
            )
            self.loaded = True

    async def process_project_file(
        self, xknx: XKNX, file_id: str, password: str
    ) -> None:
        """Process an uploaded project file."""

        def _parse_project() -> KNXProjectModel:
            with process_uploaded_file(self.hass, file_id) as file_path:
                xknxproj = XKNXProj(
                    file_path,
                    password=password,
                    language=self.hass.config.language,
                )
                return xknxproj.parse()

        project = await self.hass.async_add_executor_job(_parse_project)
        await self._store.async_save(project)
        await self.load_project(xknx, data=project)

    async def remove_project_file(self) -> None:
        """Remove project file from storage."""
        await self._store.async_remove()
        self.initial_state()

    async def get_knxproject(self) -> KNXProjectModel | None:
        """Load the project file from local storage."""
        return await self._store.async_load()

    def get_address_format(self) -> GroupAddressType:
        """Return the address format for group addresses used in the project."""
        if self.info:
            match self.info["group_address_style"]:
                case XknxProjectGroupAddressStyle.TWOLEVEL.value:
                    return GroupAddressType.SHORT
                case XknxProjectGroupAddressStyle.FREE.value:
                    return GroupAddressType.FREE
        return GroupAddressType.LONG
