"""Support for Verisure alarm control panels."""
from __future__ import annotations

import asyncio

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ALARM_ARMING, STATE_ALARM_DISARMING
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALARM_STATE_TO_HA, CONF_GIID, DOMAIN, LOGGER
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verisure alarm control panel from a config entry."""
    async_add_entities([VerisureAlarm(coordinator=hass.data[DOMAIN][entry.entry_id])])


class VerisureAlarm(
    CoordinatorEntity[VerisureDataUpdateCoordinator], AlarmControlPanelEntity
):
    """Representation of a Verisure alarm status."""

    _attr_code_format = CodeFormat.NUMBER
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name="Verisure Alarm",
            manufacturer="Verisure",
            model="VBox",
            identifiers={(DOMAIN, self.coordinator.entry.data[CONF_GIID])},
            configuration_url="https://mypages.verisure.com",
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self.coordinator.entry.data[CONF_GIID]

    async def _async_set_arm_state(
        self, state: str, command_data: dict[str, str | dict[str, str]]
    ) -> None:
        """Send set arm state command."""
        arm_state = await self.hass.async_add_executor_job(
            self.coordinator.verisure.request, command_data
        )
        LOGGER.debug("Verisure set arm state %s", state)
        result = None
        while result is None:
            await asyncio.sleep(0.5)
            transaction = await self.hass.async_add_executor_job(
                self.coordinator.verisure.request,
                self.coordinator.verisure.poll_arm_state(
                    list(arm_state["data"].values())[0], state
                ),
            )
            result = (
                transaction.get("data", {})
                .get("installation", {})
                .get("armStateChangePollResult", {})
                .get("result")
            )

        await self.coordinator.async_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._attr_state = STATE_ALARM_DISARMING
        self.async_write_ha_state()
        await self._async_set_arm_state(
            "DISARMED", self.coordinator.verisure.disarm(code)
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._attr_state = STATE_ALARM_ARMING
        self.async_write_ha_state()
        await self._async_set_arm_state(
            "ARMED_HOME", self.coordinator.verisure.arm_home(code)
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._attr_state = STATE_ALARM_ARMING
        self.async_write_ha_state()
        await self._async_set_arm_state(
            "ARMED_AWAY", self.coordinator.verisure.arm_away(code)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_state = ALARM_STATE_TO_HA.get(
            self.coordinator.data["alarm"]["statusType"]
        )
        self._attr_changed_by = self.coordinator.data["alarm"].get("name")
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
