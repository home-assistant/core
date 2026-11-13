"""Family coordinator for BroadLink Magic."""

import logging
from typing import Any, override

from broadlink_magic import (
    Family,
    GatewaySet,
    ImportedDevice,
    encode_ac_attribute,
    parse_device_upload,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _short_addr(device: ImportedDevice) -> int:
    """Return the FastCon short address of an imported device."""
    if device.short_addr is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_not_addressable",
            translation_placeholders={"device": device.name},
        )
    return device.short_addr


def _ensure_sent(sent: int) -> None:
    """Raise when no gateway accepted a command."""
    if sent == 0:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="gateway_offline",
        )


type BroadLinkMagicConfigEntry = ConfigEntry[FamilyCoordinator]


class FamilyCoordinator(DataUpdateCoordinator[GatewaySet]):
    """Track all online gateways for one imported family."""

    config_entry: BroadLinkMagicConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BroadLinkMagicConfigEntry,
        family: Family,
        gateway_set: GatewaySet,
    ) -> None:
        """Initialize the family coordinator."""
        self.family = family
        self.gateway_set = gateway_set
        self.device_states: dict[str, dict[str, Any]] = {}
        self.report_serials: dict[str, int] = {}
        self.gateway_set.set_report_callback(self._handle_fastcon_report)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{family.family_id}",
            update_interval=UPDATE_INTERVAL,
        )

    def _handle_fastcon_report(self, short_addr: int, command: bytes) -> None:
        """Map an Industry status upload to its imported device."""
        device = next(
            (
                candidate
                for candidate in self.family.devices
                if candidate.short_addr == short_addr
                and candidate.ble_device_type.upper() != "GROUP"
            ),
            None,
        )
        if device is None:
            _LOGGER.debug(
                "FastCon report for unknown short address %s",
                short_addr,
            )
            return
        values = parse_device_upload(device, command)
        if not values:
            _LOGGER.debug(
                "Ignored %s upload for %s: %s",
                device.ble_category or device.effective_pid,
                device.name,
                command.hex(),
            )
            return
        self.device_states.setdefault(device.stable_id, {}).update(values)
        self.report_serials[device.stable_id] = (
            self.report_serials.get(device.stable_id, 0) + 1
        )
        _LOGGER.debug(
            "Updated %s from gateway report: %s",
            device.name,
            values,
        )
        self.async_set_updated_data(self.gateway_set)

    @override
    async def _async_update_data(self) -> GatewaySet:
        """Expire stale inbound sessions without blocking offline setup."""
        self.gateway_set.expire_sessions()
        return self.gateway_set

    def room_name(self, room_id: int | None) -> str | None:
        """Return the imported room name for a room ID."""
        if room_id is None:
            return None
        return next(
            (room.name for room in self.family.rooms if room.room_id == room_id),
            None,
        )

    async def async_send_ac(
        self,
        device: ImportedDevice,
        attributes: list[tuple[str, int]],
    ) -> None:
        """Send one or more single-attribute AC commands."""
        await self.async_send_payloads(
            device,
            [encode_ac_attribute(attribute, value) for attribute, value in attributes],
        )

    async def async_send_payloads(
        self,
        device: ImportedDevice,
        payloads: list[bytes],
    ) -> None:
        """Send device payloads and request fresh status."""
        short_addr = _short_addr(device)
        sent = await self.gateway_set.send_remote_payloads(short_addr, payloads)
        _ensure_sent(sent)
        await self.gateway_set.send_status_query([short_addr])
