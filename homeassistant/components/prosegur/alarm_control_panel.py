"""Support for Prosegur alarm control panels."""

from __future__ import annotations

import logging

from pyprosegur.auth import Auth
from pyprosegur.installation import Installation, Status

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

STATE_MAPPING = {
    Status.DISARMED: AlarmControlPanelState.DISARMED,
    Status.ARMED: AlarmControlPanelState.ARMED_AWAY,
    Status.PARTIALLY: AlarmControlPanelState.ARMED_HOME,
    Status.ERROR_PARTIALLY: AlarmControlPanelState.ARMED_HOME,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Prosegur alarm control panel platform."""

    _installation = await Installation.retrieve(
        hass.data[DOMAIN][entry.entry_id], entry.data["contract"]
    )
    async_add_entities(
        [
            ProsegurAlarm(entry.data["contract"], hass.data[DOMAIN][entry.entry_id]),
            *[
                ProsegurAlarm(
                    entry.data["contract"], hass.data[DOMAIN][entry.entry_id], partition
                )
                for partition in _installation.partitions
            ],
        ],
        update_before_add=True,
    )


class ProsegurAlarm(AlarmControlPanelEntity):
    """Representation of a Prosegur alarm status."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )
    _attr_has_entity_name = True
    _attr_name = None
    _installation: Installation

    def __init__(
        self,
        contract: str,
        auth: Auth,
        partition: Partition | None = None,
    ) -> None:
        """Initialize the Prosegur alarm panel."""
        self._changed_by = None

        self.contract = contract
        self._partition = partition
        self._auth = auth

        self._attr_code_arm_required = False
        self._attr_unique_id = f"{contract}-{partition.id}" if partition else contract
        self._attr_name = partition.name if partition else f"Contract {contract}"

        self._attr_device_info = DeviceInfo(
            name=f"Contract {contract} {partition.name if partition else ''}".strip(),
            manufacturer="Prosegur",
            model="smart",
            identifiers={(DOMAIN, contract)},
            configuration_url="https://smart.prosegur.com",
        )

    async def async_update(self) -> None:
        """Update alarm status."""

        try:
            self._installation = await Installation.retrieve(self._auth, self.contract)
        except ConnectionError as err:
            _LOGGER.error(err)
            self._attr_available = False
            return

        if self._partition:
            partition_status = next(
                (
                    p.status
                    for p in self._installation.partitions
                    if p.id == self._partition.id
                ),
                self._installation.status,
            )
            self._attr_alarm_state = STATE_MAPPING.get(partition_status)
        else:
            self._attr_alarm_state = STATE_MAPPING.get(self._installation.status)

        self._attr_available = True

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._installation.disarm(self._auth, self._partition)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._installation.arm_partially(self._auth, self._partition)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._installation.arm(self._auth, self._partition)
