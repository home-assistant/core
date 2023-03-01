"""The Open Thread Border Router integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import dataclasses
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar

import aiohttp
import python_otbr_api
from python_otbr_api import tlv_parser
from python_otbr_api.pskc import compute_pskc

from homeassistant.components.thread import async_add_dataset
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DOMAIN

_R = TypeVar("_R")
_P = ParamSpec("_P")

INSECURE_NETWORK_KEYS = (
    # Thread web UI default
    bytes.fromhex("00112233445566778899AABBCCDDEEFF"),
)

INSECURE_PASSPHRASES = (
    # Thread web UI default
    "j01Nme",
    # Thread documentation default
    "J01NME",
)


def _handle_otbr_error(
    func: Callable[Concatenate[OTBRData, _P], Coroutine[Any, Any, _R]]
) -> Callable[Concatenate[OTBRData, _P], Coroutine[Any, Any, _R]]:
    """Handle OTBR errors."""

    @wraps(func)
    async def _func(self: OTBRData, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except python_otbr_api.OTBRError as exc:
            raise HomeAssistantError("Failed to call OTBR API") from exc

    return _func


@dataclasses.dataclass
class OTBRData:
    """Container for OTBR data."""

    url: str
    api: python_otbr_api.OTBR

    @_handle_otbr_error
    async def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the router."""
        return await self.api.set_enabled(enabled)

    @_handle_otbr_error
    async def get_active_dataset_tlvs(self) -> bytes | None:
        """Get current active operational dataset in TLVS format, or None."""
        return await self.api.get_active_dataset_tlvs()

    @_handle_otbr_error
    async def create_active_dataset(
        self, dataset: python_otbr_api.OperationalDataSet
    ) -> None:
        """Create an active operational dataset."""
        return await self.api.create_active_dataset(dataset)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Open Thread Border Router component."""
    websocket_api.async_setup(hass)
    return True


def _warn_on_default_network_settings(
    hass: HomeAssistant, entry: ConfigEntry, dataset_tlvs: bytes
) -> None:
    """Warn user if insecure default network settings are used."""
    dataset = tlv_parser.parse_tlv(dataset_tlvs.hex())
    insecure = False

    if (
        network_key := dataset.get(tlv_parser.MeshcopTLVType.NETWORKKEY)
    ) is not None and bytes.fromhex(network_key) in INSECURE_NETWORK_KEYS:
        insecure = True
    if (
        not insecure
        and tlv_parser.MeshcopTLVType.EXTPANID in dataset
        and tlv_parser.MeshcopTLVType.NETWORKNAME in dataset
        and tlv_parser.MeshcopTLVType.PSKC in dataset
    ):
        ext_pan_id = dataset[tlv_parser.MeshcopTLVType.EXTPANID]
        network_name = dataset[tlv_parser.MeshcopTLVType.NETWORKNAME]
        pskc = bytes.fromhex(dataset[tlv_parser.MeshcopTLVType.PSKC])
        for passphrase in INSECURE_PASSPHRASES:
            if pskc == compute_pskc(ext_pan_id, network_name, passphrase):
                insecure = True
                break

    if insecure:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"insecure_thread_network_{entry.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="insecure_thread_network",
        )
    else:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            f"insecure_thread_network_{entry.entry_id}",
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Open Thread Border Router config entry."""
    api = python_otbr_api.OTBR(entry.data["url"], async_get_clientsession(hass), 10)

    otbrdata = OTBRData(entry.data["url"], api)
    try:
        dataset_tlvs = await otbrdata.get_active_dataset_tlvs()
    except (
        HomeAssistantError,
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ) as err:
        raise ConfigEntryNotReady("Unable to connect") from err
    if dataset_tlvs:
        _warn_on_default_network_settings(hass, entry, dataset_tlvs)
        await async_add_dataset(hass, entry.title, dataset_tlvs.hex())

    hass.data[DOMAIN] = otbrdata

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN)
    return True


async def async_get_active_dataset_tlvs(hass: HomeAssistant) -> bytes | None:
    """Get current active operational dataset in TLVS format, or None.

    Returns None if there is no active operational dataset.
    Raises if the http status is 400 or higher or if the response is invalid.
    """
    if DOMAIN not in hass.data:
        raise HomeAssistantError("OTBR API not available")

    data: OTBRData = hass.data[DOMAIN]
    return await data.get_active_dataset_tlvs()
