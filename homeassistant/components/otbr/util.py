"""Utility functions for the Open Thread Border Router integration."""

from collections.abc import Callable, Coroutine
import dataclasses
from functools import wraps
from http import HTTPStatus
import logging
import random
from typing import TYPE_CHECKING, Any, Concatenate, cast

import aiohttp
import python_otbr_api
from python_otbr_api import PENDING_DATASET_DELAY_TIMER, tlv_parser
from python_otbr_api.pskc import compute_pskc
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    MultiprotocolAddonManager,
    get_multiprotocol_addon_manager,
    is_multiprotocol_url,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

if TYPE_CHECKING:
    from . import OTBRConfigEntry

_LOGGER = logging.getLogger(__name__)


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


class GetBorderAgentIdNotSupported(HomeAssistantError):
    """Raised from python_otbr_api.GetBorderAgentIdNotSupportedError."""


class EphemeralKeyNotSupported(HomeAssistantError):
    """Raised when the router does not expose ephemeral key mode."""


# A router without the ephemeral key routes answers with 404, but ot-br-posix
# builds between #2733 and #3524 turn every PUT error into 405 (ot-br-posix#3522).
EPHEMERAL_KEY_UNSUPPORTED_STATUS = (
    HTTPStatus.NOT_FOUND,
    HTTPStatus.METHOD_NOT_ALLOWED,
)


def compose_default_network_name(pan_id: int) -> str:
    """Generate a default network name."""
    return f"ha-thread-{pan_id:04x}"


def generate_random_pan_id() -> int:
    """Generate a random PAN ID."""
    # PAN ID is 2 bytes, 0xffff is reserved for broadcast
    return random.randint(0, 0xFFFE)


def _handle_otbr_error[**_P, _R](
    func: Callable[Concatenate[OTBRData, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[OTBRData, _P], Coroutine[Any, Any, _R]]:
    """Handle OTBR errors."""

    @wraps(func)
    async def _func(self: OTBRData, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except (python_otbr_api.OTBRError, aiohttp.ClientError, TimeoutError) as exc:
            raise HomeAssistantError("Failed to call OTBR API") from exc

    return _func


@dataclasses.dataclass
class OTBRData:
    """Container for OTBR data."""

    url: str
    api: python_otbr_api.OTBR
    entry_id: str
    ephemeral_key_supported: bool = False

    @_handle_otbr_error
    async def factory_reset(self, hass: HomeAssistant) -> None:
        """Reset the router."""
        try:
            await self.api.factory_reset()
        except python_otbr_api.FactoryResetNotSupportedError:
            _LOGGER.warning(
                "OTBR does not support factory reset, attempting to delete dataset"
            )
            await self.delete_active_dataset()
        await update_unique_id(
            hass,
            hass.config_entries.async_get_entry(self.entry_id),
            await self.get_border_agent_id(),
        )

    @_handle_otbr_error
    async def get_border_agent_id(self) -> bytes:
        """Get the border agent ID or None if not supported by the router."""
        try:
            return await self.api.get_border_agent_id()
        except python_otbr_api.GetBorderAgentIdNotSupportedError as exc:
            raise GetBorderAgentIdNotSupported from exc

    @_handle_otbr_error
    async def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the router."""
        return await self.api.set_enabled(enabled)

    @_handle_otbr_error
    async def get_active_dataset(self) -> python_otbr_api.ActiveDataSet | None:
        """Get current active operational dataset, or None."""
        return await self.api.get_active_dataset()

    @_handle_otbr_error
    async def get_active_dataset_tlvs(self) -> bytes | None:
        """Get current active operational dataset in TLVS format, or None."""
        return await self.api.get_active_dataset_tlvs()

    @_handle_otbr_error
    async def get_pending_dataset_tlvs(self) -> bytes | None:
        """Get current pending operational dataset in TLVS format, or None."""
        return await self.api.get_pending_dataset_tlvs()

    @_handle_otbr_error
    async def create_active_dataset(
        self, dataset: python_otbr_api.ActiveDataSet
    ) -> None:
        """Create an active operational dataset."""
        return await self.api.create_active_dataset(dataset)

    @_handle_otbr_error
    async def delete_active_dataset(self) -> None:
        """Delete the active operational dataset."""
        return await self.api.delete_active_dataset()

    @_handle_otbr_error
    async def set_active_dataset_tlvs(self, dataset: bytes) -> None:
        """Set current active operational dataset in TLVS format."""
        await self.api.set_active_dataset_tlvs(dataset)

    @_handle_otbr_error
    async def set_channel(
        self, channel: int, delay: float = PENDING_DATASET_DELAY_TIMER / 1000
    ) -> None:
        """Set current channel."""
        await self.api.set_channel(channel, delay=int(delay * 1000))

    @_handle_otbr_error
    async def get_extended_address(self) -> bytes:
        """Get extended address (EUI-64)."""
        return await self.api.get_extended_address()

    @_handle_otbr_error
    async def get_coprocessor_version(self) -> str:
        """Get coprocessor firmware version."""
        return await self.api.get_coprocessor_version()

    @_handle_otbr_error
    async def get_ephemeral_key_supported(self, hass: HomeAssistant) -> bool:
        """Return whether the router supports ephemeral key mode.

        Like activate_ephemeral_key, this calls the REST endpoint directly;
        move this to the library once python-otbr-api#267 is released.
        """
        session = async_get_clientsession(hass)
        response = await session.get(
            f"{self.url}/node/ba-epskc/state",
            timeout=aiohttp.ClientTimeout(total=10),
        )
        # Only 200 proves support; never fail setup over an optional feature
        return response.status == HTTPStatus.OK

    @_handle_otbr_error
    async def activate_ephemeral_key(
        self, hass: HomeAssistant, lifetime: int
    ) -> tuple[str, int]:
        """Activate ephemeral key mode, returning the passcode and its UDP port.

        The lifetime is in milliseconds, as the OpenThread border agent API
        takes it. These endpoints are not in python-otbr-api yet, they are
        called directly to follow home-assistant-libs/python-otbr-api#267;
        move this to the library once that is released.
        """
        session = async_get_clientsession(hass)
        timeout = aiohttp.ClientTimeout(total=10)

        # The feature has to be enabled before a key can be activated
        response = await session.put(
            f"{self.url}/node/ba-epskc/state",
            json="enable",
            timeout=timeout,
        )
        if response.status in EPHEMERAL_KEY_UNSUPPORTED_STATUS:
            raise EphemeralKeyNotSupported
        if response.status != HTTPStatus.OK:
            raise python_otbr_api.OTBRError(f"unexpected http status {response.status}")

        async def activate() -> aiohttp.ClientResponse:
            return await session.post(
                f"{self.url}/node/ba-epskc/key",
                json={"lifetime": lifetime},
                timeout=timeout,
            )

        response = await activate()
        if response.status == HTTPStatus.CONFLICT:
            # A key is already active, and one can only be started from the
            # stopped state, so drop it and ask for a replacement.
            delete_response = await session.delete(
                f"{self.url}/node/ba-epskc/key", timeout=timeout
            )
            if delete_response.status != HTTPStatus.OK:
                raise python_otbr_api.OTBRError(
                    "failed to replace the active ephemeral key: "
                    f"unexpected http status {delete_response.status}"
                )
            response = await activate()

        if response.status in EPHEMERAL_KEY_UNSUPPORTED_STATUS:
            raise EphemeralKeyNotSupported
        if response.status != HTTPStatus.OK:
            raise python_otbr_api.OTBRError(f"unexpected http status {response.status}")

        try:
            activation = await response.json()
            return activation["tap"], activation["port"]
        except (ValueError, KeyError, TypeError) as exc:
            raise python_otbr_api.OTBRError("unexpected API response") from exc

    @_handle_otbr_error
    async def deactivate_ephemeral_key(self, hass: HomeAssistant) -> None:
        """Deactivate the active ephemeral key, if any.

        Like activate_ephemeral_key, this calls the REST endpoint directly;
        move this to the library once python-otbr-api#267 is released.
        """
        session = async_get_clientsession(hass)
        response = await session.delete(
            f"{self.url}/node/ba-epskc/key",
            timeout=aiohttp.ClientTimeout(total=10),
        )
        if response.status in EPHEMERAL_KEY_UNSUPPORTED_STATUS:
            raise EphemeralKeyNotSupported
        if response.status != HTTPStatus.OK:
            raise python_otbr_api.OTBRError(f"unexpected http status {response.status}")


async def get_allowed_channel(hass: HomeAssistant, otbr_url: str) -> int | None:
    """Return the allowed channel, or None if there's no restriction."""
    if not is_multiprotocol_url(otbr_url):
        # The OTBR is not sharing the radio, no restriction
        return None

    multipan_manager: MultiprotocolAddonManager = await get_multiprotocol_addon_manager(
        hass
    )
    return multipan_manager.async_get_channel()


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

    if (channel_s := dataset.get(MeshcopTLVType.CHANNEL)) is None:
        delete_issue()
        return
    channel = cast(tlv_parser.Channel, channel_s).channel

    if channel == allowed_channel:
        delete_issue()
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"otbr_zha_channel_collision_{otbrdata.entry_id}",
        is_fixable=False,
        is_persistent=False,
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
        network_key := dataset.get(MeshcopTLVType.NETWORKKEY)
    ) is not None and network_key.data in INSECURE_NETWORK_KEYS:
        insecure = True
    if (
        not insecure
        and MeshcopTLVType.EXTPANID in dataset
        and MeshcopTLVType.NETWORKNAME in dataset
        and MeshcopTLVType.PSKC in dataset
    ):
        ext_pan_id = dataset[MeshcopTLVType.EXTPANID]
        network_name = cast(tlv_parser.NetworkName, dataset[MeshcopTLVType.NETWORKNAME])
        pskc = dataset[MeshcopTLVType.PSKC].data
        for passphrase in INSECURE_PASSPHRASES:
            if pskc == compute_pskc(ext_pan_id.data, network_name.name, passphrase):
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


async def update_unique_id(
    hass: HomeAssistant, entry: OTBRConfigEntry | None, border_agent_id: bytes
) -> None:
    """Update the config entry's unique_id if not matching."""
    border_agent_id_hex = border_agent_id.hex()
    if entry and entry.source == SOURCE_USER and entry.unique_id != border_agent_id_hex:
        _LOGGER.debug(
            "Updating unique_id of entry %s from %s to %s",
            entry.entry_id,
            entry.unique_id,
            border_agent_id_hex,
        )
        hass.config_entries.async_update_entry(entry, unique_id=border_agent_id_hex)
