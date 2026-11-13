"""Handle KNX project data."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any, Final

from awesomeversion import AwesomeVersion, AwesomeVersionException
import probatio
from xknx import XKNX
from xknx.dpt import DPTBase
from xknx.exceptions import CouldNotParseAddress
from xknx.telegram.address import DeviceAddressableType, GroupAddress, GroupAddressType
from xknxproject import XKNXProj
from xknxproject.__version__ import __version__ as XKNXPROJECT_VERSION
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN, KNX_MODULE_KEY

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}/knx_project.json"


def _group_addresses(value: dict[str, Any]) -> dict[str, Any]:
    """Validate group addresses beyond their types."""
    for key, group_address in value.items():
        address = group_address["address"]
        try:
            GroupAddress(address)
        except CouldNotParseAddress as err:
            raise probatio.Invalid(f"invalid group address `{address}`") from err
        if key != address:
            raise probatio.Invalid(f"group address `{address}` is keyed as `{key}`")
    return value


def _info(value: dict[str, Any]) -> dict[str, Any]:
    """Validate the project info beyond its types."""
    probatio.In([style.value for style in XknxProjectGroupAddressStyle])(
        value["group_address_style"]
    )
    return value


# Project data in the format of the installed xknxproject, built from its types.
PROJECT_DATA_SCHEMA: Final = probatio.TypedDictSchema(
    KNXProjectModel,
    {"group_addresses": _group_addresses, "info": _info},
    extra=probatio.ALLOW_EXTRA,
)


def _address_in_style(raw: int, style: str) -> str:
    """Return a group address as xknx shows it in a project of `style`."""
    if style == XknxProjectGroupAddressStyle.FREE.value:
        return str(raw)
    main = (raw >> 11) & GroupAddress.MAX_MAIN
    if style == XknxProjectGroupAddressStyle.TWOLEVEL.value:
        return f"{main}/{raw & GroupAddress.MAX_SUB_SHORT}"
    middle = (raw >> 8) & GroupAddress.MAX_MIDDLE
    return f"{main}/{middle}/{raw & GroupAddress.MAX_SUB_LONG}"


def _check_address_style(project: KNXProjectModel) -> None:
    """Validate that the group addresses are written in the project's style.

    The integration looks addresses up as xknx shows them in that style.
    """
    style = project["info"]["group_address_style"]
    for key, group_address in project["group_addresses"].items():
        address = group_address["address"]
        if _address_in_style(GroupAddress(address).raw, style) != address:
            raise probatio.Invalid(
                f"group address `{address}` is not written in the {style} style "
                f"at 'group_addresses['{key}'].address'"
            )


def _check_parser_version(project: Any) -> None:
    """Refuse data of a major version of xknxproject other than the installed one.

    Data without a version is left to the schema to report.
    """
    info = project.get("info") if isinstance(project, Mapping) else None
    version = info.get("xknxproject_version") if isinstance(info, Mapping) else None
    if not isinstance(version, str):
        return
    try:
        compatible = (
            AwesomeVersion(version).major == AwesomeVersion(XKNXPROJECT_VERSION).major
        )
    except AwesomeVersionException:
        compatible = False
    if not compatible:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="project_data_incompatible",
            translation_placeholders={
                "version": version,
                "installed_version": XKNXPROJECT_VERSION,
            },
        )


def validate_project_data(project: Any) -> KNXProjectModel:
    """Validate project data in the format of the installed xknxproject.

    Raises HomeAssistantError when the data was created for another major
    version of xknxproject, or doesn't have its format.
    """
    _check_parser_version(project)
    try:
        data = PROJECT_DATA_SCHEMA(project)
        _check_address_style(data)
    except probatio.Invalid as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="project_data_invalid",
            translation_placeholders={"error": str(err)},
        ) from err
    return data


async def async_set_project(hass: HomeAssistant, project: Mapping[str, Any]) -> None:
    """Replace the KNX project with project data in the format of xknxproject.

    For integrations and tools that provide project data from another source
    than a project file, eg. a project editor keeping it up to date while it is
    edited. The data is validated first; it is stored and loaded as an uploaded
    project file is.

    Raises HomeAssistantError when the KNX integration is not loaded, or the
    data is invalid or incompatible. The current project is kept then.
    """
    if (knx_module := hass.data.get(KNX_MODULE_KEY)) is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="integration_not_loaded"
        )
    data = validate_project_data(project)
    await knx_module.project.async_store_project(knx_module.xknx, data)


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
    _project: KNXProjectModel | None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize project data."""
        self.hass = hass
        self._store = Store[KNXProjectModel](hass, STORAGE_VERSION, STORAGE_KEY)
        # Serializes the cached project against upload and removal, so a load
        # in flight cannot resurrect a project that was replaced or removed.
        self._project_lock = asyncio.Lock()

        self.initial_state()

    def initial_state(self) -> None:
        """Set initial state for project data."""
        self.loaded = False
        self.devices = {}
        self.group_addresses = {}
        self.info = None
        self._project = None

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
            # Replace rather than extend: addresses of a previous project don't stay.
            group_addresses: dict[str, GroupAddressInfo] = {}

            for ga_model in project["group_addresses"].values():
                ga_info = _create_group_address_info(ga_model)
                group_addresses[ga_info.address] = ga_info
                if (dpt_model := ga_model.get("dpt")) is not None:
                    xknx_ga_dict[ga_model["address"]] = dpt_model

            xknx.group_address_dpt.set(xknx_ga_dict)
            self.group_addresses = group_addresses

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
        await self.async_store_project(xknx, project)

    async def async_store_project(self, xknx: XKNX, project: KNXProjectModel) -> None:
        """Store and load parsed project data, replacing the current project."""
        async with self._project_lock:
            await self._store.async_save(project)
            # Invalidate rather than populate: whether the full project is held
            # is left to whoever asks for it.
            self._project = None
            await self.load_project(xknx, data=project)

    async def remove_project_file(self) -> None:
        """Remove project file from storage."""
        async with self._project_lock:
            await self._store.async_remove()
            self.initial_state()

    async def get_knxproject(self) -> KNXProjectModel | None:
        """Return the full project, reading it from local storage on first use.

        `Store.async_load` skips its own cache for keys containing "/", so it
        would re-parse the multi-megabyte file on every call.
        """
        async with self._project_lock:
            if self._project is None:
                self._project = await self._store.async_load()
            return self._project

    def get_address_format(self) -> GroupAddressType:
        """Return the address format for group addresses used in the project."""
        if self.info:
            match self.info["group_address_style"]:
                case XknxProjectGroupAddressStyle.TWOLEVEL.value:
                    return GroupAddressType.SHORT
                case XknxProjectGroupAddressStyle.FREE.value:
                    return GroupAddressType.FREE
        return GroupAddressType.LONG
