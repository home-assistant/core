"""Utility functions for the Open Thread Border Router integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
import contextlib
import dataclasses
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar

import python_otbr_api
from python_otbr_api import tlv_parser
from python_otbr_api.pskc import compute_pskc

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
    multi_pan_addon_using_device,
)
from homeassistant.components.homeassistant_yellow import RADIO_DEVICE as YELLOW_RADIO
from homeassistant.components.zha import api as zha_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_R = TypeVar("_R")
_P = ParamSpec("_P")

INFO_URL_SKY_CONNECT = (
    "https://skyconnect.home-assistant.io/multiprotocol-channel-missmatch"
)
INFO_URL_YELLOW = "https://yellow.home-assistant.io/multiprotocol-channel-missmatch"

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
    entry_id: str

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

    @_handle_otbr_error
    async def set_active_dataset_tlvs(self, dataset: bytes) -> None:
        """Set current active operational dataset in TLVS format."""
        await self.api.set_active_dataset_tlvs(dataset)

    @_handle_otbr_error
    async def get_extended_address(self) -> bytes:
        """Get extended address (EUI-64)."""
        return await self.api.get_extended_address()


def _get_zha_url(hass: HomeAssistant) -> str | None:
    """Get ZHA radio path, or None if there's no ZHA config entry."""
    with contextlib.suppress(ValueError):
        return zha_api.async_get_radio_path(hass)
    return None


async def _get_zha_channel(hass: HomeAssistant) -> int | None:
    """Get ZHA channel, or None if there's no ZHA config entry."""
    zha_network_settings: zha_api.NetworkBackup | None
    with contextlib.suppress(ValueError):
        zha_network_settings = await zha_api.async_get_network_settings(hass)
    if not zha_network_settings:
        return None
    channel: int = zha_network_settings.network_info.channel
    # ZHA uses channel 0 when no channel is set
    return channel or None


async def get_allowed_channel(hass: HomeAssistant, otbr_url: str) -> int | None:
    """Return the allowed channel, or None if there's no restriction."""
    if not is_multiprotocol_url(otbr_url):
        # The OTBR is not sharing the radio, no restriction
        return None

    zha_url = _get_zha_url(hass)
    if not zha_url or not is_multiprotocol_url(zha_url):
        # ZHA is not configured or not sharing the radio with this OTBR, no restriction
        return None

    return await _get_zha_channel(hass)


async def _warn_on_channel_collision(
    hass: HomeAssistant, otbrdata: OTBRData, dataset_tlvs: bytes
) -> None:
    """Warn user if OTBR and ZHA attempt to use different channels."""

    def delete_issue() -> None:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            f"otbr_zha_channel_collision_{otbrdata.entry_id}",
        )

    if (allowed_channel := await get_allowed_channel(hass, otbrdata.url)) is None:
        delete_issue()
        return

    dataset = tlv_parser.parse_tlv(dataset_tlvs.hex())

    if (channel_s := dataset.get(tlv_parser.MeshcopTLVType.CHANNEL)) is None:
        delete_issue()
        return
    try:
        channel = int(channel_s, 16)
    except ValueError:
        delete_issue()
        return

    if channel == allowed_channel:
        delete_issue()
        return

    yellow = await multi_pan_addon_using_device(hass, YELLOW_RADIO)
    learn_more_url = INFO_URL_YELLOW if yellow else INFO_URL_SKY_CONNECT

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"otbr_zha_channel_collision_{otbrdata.entry_id}",
        is_fixable=False,
        is_persistent=False,
        learn_more_url=learn_more_url,
        severity=ir.IssueSeverity.WARNING,
        translation_key="otbr_zha_channel_collision",
        translation_placeholders={
            "otbr_channel": str(channel),
            "zha_channel": str(allowed_channel),
        },
    )


def _warn_on_default_network_settings(
    hass: HomeAssistant, otbrdata: OTBRData, dataset_tlvs: bytes
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
            f"insecure_thread_network_{otbrdata.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="insecure_thread_network",
        )
    else:
        ir.async_delete_issue(
            hass,
            DOMAIN,
            f"insecure_thread_network_{otbrdata.entry_id}",
        )


async def update_issues(
    hass: HomeAssistant, otbrdata: OTBRData, dataset_tlvs: bytes
) -> None:
    """Raise or clear repair issues related to network settings."""
    await _warn_on_channel_collision(hass, otbrdata, dataset_tlvs)
    _warn_on_default_network_settings(hass, otbrdata, dataset_tlvs)
