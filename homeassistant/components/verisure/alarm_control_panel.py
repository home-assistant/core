"""Support for Verisure alarm control panels."""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VerisureDataUpdateCoordinator
from .const import CONF_ALARM, CONF_GIID, DOMAIN, LOGGER


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[Entity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure platform."""
    coordinator = hass.data[DOMAIN]
    alarms = []
    if int(coordinator.config.get(CONF_ALARM, 1)):
        alarms.append(VerisureAlarm(coordinator))
    add_entities(alarms)


class VerisureAlarm(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of a Verisure alarm status."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(self, coordinator: VerisureDataUpdateCoordinator) -> None:
        """Initialize the Verisure alarm panel."""
        super().__init__(coordinator)
        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the device."""
        giid = self.coordinator.config.get(CONF_GIID)
        if giid is not None:
            aliass = {
                i["giid"]: i["alias"] for i in self.coordinator.session.installations
            }
            if giid in aliass:
                return "{} alarm".format(aliass[giid])

            LOGGER.error("Verisure installation giid not found: %s", giid)

        return "{} alarm".format(self.coordinator.session.installations[0]["alias"])

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        status = self.coordinator.get_first("$.armState.statusType")
        if status == "DISARMED":
            self._state = STATE_ALARM_DISARMED
        elif status == "ARMED_HOME":
            self._state = STATE_ALARM_ARMED_HOME
        elif status == "ARMED_AWAY":
            self._state = STATE_ALARM_ARMED_AWAY
        elif status == "PENDING":
            self._state = STATE_ALARM_PENDING
        else:
            LOGGER.error("Unknown alarm state %s", status)

        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    @property
    def code_format(self) -> str:
        """Return one or more digits/characters."""
        return FORMAT_NUMBER

    @property
    def changed_by(self) -> str | None:
        """Return the last change triggered by."""
        return self.coordinator.get_first("$.armState.name")

    async def _async_set_arm_state(self, state: str, code: str | None = None) -> None:
        """Send set arm state command."""
        arm_state = await self.hass.async_add_executor_job(
            self.coordinator.session.set_arm_state, code, state
        )
        LOGGER.debug("Verisure set arm state %s", state)
        transaction = {}
        while "result" not in transaction:
            await asyncio.sleep(0.5)
            transaction = await self.hass.async_add_executor_job(
                self.coordinator.session.get_arm_state_transaction,
                arm_state["armStateChangeTransactionId"],
            )

        await self.coordinator.async_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._async_set_arm_state("DISARMED", code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._async_set_arm_state("ARMED_HOME", code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._async_set_arm_state("ARMED_AWAY", code)
