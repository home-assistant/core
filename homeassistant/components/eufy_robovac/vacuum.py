"""Vacuum platform for Eufy RoboVac."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    EufyRoboVacConfigEntry,
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DEFAULT_PROTOCOL_VERSION,
    DOMAIN,
    RoboVacCommand,
    dps_update_signal,
)
from .local_api import EufyRoboVacLocalApi, EufyRoboVacLocalApiError
from .model_mappings import MODEL_MAPPINGS, RoboVacModelMapping

_LOGGER = logging.getLogger(__name__)

_STATUS_TO_ACTIVITY: dict[str, VacuumActivity] = {
    "charge_done": VacuumActivity.DOCKED,
    "chargecompleted": VacuumActivity.DOCKED,
    "chargego": VacuumActivity.RETURNING,
    "charging": VacuumActivity.DOCKED,
    "cleaning": VacuumActivity.CLEANING,
    "completed": VacuumActivity.DOCKED,
    "docking": VacuumActivity.RETURNING,
    "goto_charge": VacuumActivity.RETURNING,
    "mop_clean": VacuumActivity.CLEANING,
    "paused": VacuumActivity.PAUSED,
    "recharge": VacuumActivity.RETURNING,
    "sleep": VacuumActivity.IDLE,
    "sleeping": VacuumActivity.IDLE,
    "smart": VacuumActivity.CLEANING,
    "smart_clean": VacuumActivity.CLEANING,
    "spot_clean": VacuumActivity.CLEANING,
    "standby": VacuumActivity.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EufyRoboVacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eufy RoboVac entities from a config entry."""
    model_code: str = entry.data[CONF_MODEL]
    mapping = MODEL_MAPPINGS[model_code]

    async_add_entities([EufyRoboVacEntity(entry=entry, mapping=mapping)])


class EufyRoboVacEntity(StateVacuumEntity):
    """Representation of a Eufy RoboVac vacuum entity."""

    _attr_should_poll = True

    def __init__(
        self, *, entry: EufyRoboVacConfigEntry, mapping: RoboVacModelMapping
    ) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._mapping = mapping

        self._attr_unique_id = entry.data[CONF_ID]
        self._attr_name = entry.data[CONF_NAME]
        self._attr_available = True
        self._attr_activity = VacuumActivity.IDLE
        self._attr_fan_speed = "standard"
        self._attr_fan_speed_list = list(mapping.fan_speed_values)
        self._attr_supported_features = (
            VacuumEntityFeature.START
            | VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.SEND_COMMAND
            | VacuumEntityFeature.LOCATE
            | VacuumEntityFeature.STATE
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._attr_unique_id))},
            manufacturer="Eufy",
            model=mapping.display_name,
            name=self._attr_name,
        )

        self._last_status_raw: str | None = None
        self._last_error_raw: str | None = None
        self._dps: dict[str, Any] = {}
        self._api = EufyRoboVacLocalApi(
            host=entry.data[CONF_HOST],
            device_id=entry.data[CONF_ID],
            local_key=entry.data[CONF_LOCAL_KEY],
            protocol_version=entry.data.get(
                CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION
            ),
        )

    def _dps_code(self, command: RoboVacCommand) -> str:
        """Return the DPS code for a given command."""
        return str(self._mapping.commands[command])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "model_code": self._mapping.model_code,
            "model_name": self._mapping.display_name,
            "host": self._entry.data[CONF_HOST],
            "protocol_version": self._entry.data.get(
                CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION
            ),
            "local_key_present": bool(self._entry.data.get(CONF_LOCAL_KEY)),
            "status_raw": self._last_status_raw,
            "error_raw": self._last_error_raw,
        }

    @staticmethod
    def _normalize_lookup_key(value: Any) -> str:
        """Normalize raw device values for mapping lookups."""
        return str(value).strip().lower()

    def _reverse_lookup(self, mapping: dict[str, str], raw_value: Any) -> str | None:
        """Map a raw device value back to our canonical key names."""
        normalized = self._normalize_lookup_key(raw_value)
        for key, mapped_value in mapping.items():
            if self._normalize_lookup_key(mapped_value) == normalized:
                return key
        return None

    def _async_publish_dps(self, dps: dict[str, Any]) -> None:
        """Publish fresh DPS payload for sibling entities."""
        if self.hass is None:
            return

        self._entry.runtime_data["dps"] = dps

        async_dispatcher_send(self.hass, dps_update_signal(self._entry.entry_id), dps)

    async def _async_send_and_refresh(self, dps: dict[str, Any]) -> None:
        """Send DPS commands and refresh entity state."""
        try:
            await self._api.async_send_dps(self.hass, dps)
        except EufyRoboVacLocalApiError as err:
            raise HomeAssistantError(str(err)) from err

        await self.async_update()
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch state from the local vacuum API."""
        try:
            dps = await self._api.async_get_dps(self.hass)
        except EufyRoboVacLocalApiError as err:
            _LOGGER.warning("Failed updating %s: %s", self._attr_unique_id, err)
            self._attr_available = False
            return

        if not dps:
            self._attr_available = False
            return

        self._attr_available = True
        self._dps = dps
        self._async_publish_dps(dps)
        status_raw = dps.get(self._dps_code(RoboVacCommand.STATUS))
        error_raw = dps.get(self._dps_code(RoboVacCommand.ERROR))
        fan_raw = dps.get(self._dps_code(RoboVacCommand.FAN_SPEED))

        if status_raw is not None:
            self._last_status_raw = str(status_raw)
            activity = _STATUS_TO_ACTIVITY.get(
                self._normalize_lookup_key(status_raw), VacuumActivity.CLEANING
            )
            self._attr_activity = activity

        if error_raw is not None:
            self._last_error_raw = str(error_raw)
            if self._normalize_lookup_key(error_raw) not in (
                "0",
                "no_error",
                "no error",
            ):
                self._attr_activity = VacuumActivity.ERROR

        if fan_raw is not None:
            if canonical_fan := self._reverse_lookup(
                self._mapping.fan_speed_values, fan_raw
            ):
                self._attr_fan_speed = canonical_fan

    async def async_start(self) -> None:
        """Start cleaning."""
        await self._async_send_and_refresh(
            {
                self._dps_code(RoboVacCommand.START_PAUSE): True,
            }
        )

    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self._async_send_and_refresh(
            {
                self._dps_code(RoboVacCommand.START_PAUSE): False,
            }
        )

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop cleaning by returning to dock."""
        await self.async_return_to_base(**kwargs)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return vacuum to dock."""
        await self._async_send_and_refresh(
            {
                self._dps_code(RoboVacCommand.RETURN_HOME): True,
            }
        )

    async def async_locate(self, **kwargs: Any) -> None:
        """Trigger locate sound."""
        locate_code = self._dps_code(RoboVacCommand.LOCATE)
        current = self._dps.get(locate_code)
        await self._async_send_and_refresh({locate_code: not bool(current)})

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        normalized = fan_speed.lower().replace(" ", "_")
        if normalized not in self._mapping.fan_speed_values:
            raise HomeAssistantError(
                f"Unsupported fan speed '{fan_speed}' for {self._mapping.model_code}"
            )

        await self._async_send_and_refresh(
            {
                self._dps_code(RoboVacCommand.FAN_SPEED): self._mapping.fan_speed_values[
                    normalized
                ],
            }
        )

    async def async_send_command(
        self, command: str, params: list[str] | None = None, **kwargs: Any
    ) -> None:
        """Send a custom command to the vacuum.

        Supported in this MVP:
        - direct mode names: auto, small_room, spot, edge, nosweep
        """
        if command not in self._mapping.mode_values:
            raise HomeAssistantError(
                f"Unsupported command '{command}' for {self._mapping.model_code}"
            )

        await self._async_send_and_refresh(
            {
                self._dps_code(RoboVacCommand.MODE): self._mapping.mode_values[command],
            }
        )
