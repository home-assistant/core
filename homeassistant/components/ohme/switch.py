"""Platform for switch integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import COORDINATOR_ACCOUNTINFO, COORDINATOR_CHARGESESSIONS
from .entity import OhmeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches and configure coordinator."""

    coordinators = config_entry.runtime_data.coordinators

    coordinator = coordinators[COORDINATOR_CHARGESESSIONS]
    accountinfo_coordinator = coordinators[COORDINATOR_ACCOUNTINFO]
    client = config_entry.runtime_data.client

    switches = [
        OhmePauseChargeSwitch(coordinator, hass, client),
        OhmeMaxChargeSwitch(coordinator, hass, client),
    ]

    if client.cap_available():
        switches.append(OhmePriceCapSwitch(accountinfo_coordinator, hass, client))

    if client.solar_capable():
        switches.append(OhmeSolarBoostSwitch(accountinfo_coordinator, hass, client))
    if client.is_capable("buttonsLockable"):
        switches.append(
            OhmeConfigurationSwitch(
                accountinfo_coordinator,
                hass,
                client,
                "lock_buttons",
                "lock",
                "buttonsLocked",
            )
        )
    if client.is_capable("pluginsRequireApprovalMode"):
        switches.append(
            OhmeConfigurationSwitch(
                accountinfo_coordinator,
                hass,
                client,
                "require_approval",
                "check-decagram",
                "pluginsRequireApproval",
            )
        )
    if client.is_capable("stealth"):
        switches.append(
            OhmeConfigurationSwitch(
                accountinfo_coordinator,
                hass,
                client,
                "sleep_when_inactive",
                "power-sleep",
                "stealthEnabled",
            )
        )

    async_add_entities(switches, update_before_add=True)


class OhmePauseChargeSwitch(OhmeEntity, SwitchEntity):
    """Switch for pausing a charge."""

    _attr_translation_key = "pause_charge"
    _attr_icon = "mdi:pause"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Determine if charge is paused.

        We handle this differently to the sensors as the state of this switch
        is evaluated only when new data is fetched to stop the switch flicking back then forth.
        """
        if self.coordinator.data is None:
            self._attr_is_on = False
        else:
            self._attr_is_on = bool(self.coordinator.data["mode"] == "STOPPED")

        self._last_updated = utcnow()

        self.async_write_ha_state()

    async def async_turn_on(self):
        """Turn on the switch."""
        await self._client.async_pause_charge()

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_turn_off(self):
        """Turn off the switch."""
        await self._client.async_resume_charge()

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()


class OhmeMaxChargeSwitch(OhmeEntity, SwitchEntity):
    """Switch for pausing a charge."""

    _attr_translation_key = "max_charge"
    _attr_icon = "mdi:battery-arrow-up"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Determine if we are max charging."""
        if self.coordinator.data is None:
            self._attr_is_on = False
        else:
            self._attr_is_on = bool(self.coordinator.data["mode"] == "MAX_CHARGE")

        self._last_updated = utcnow()

        self.async_write_ha_state()

    async def async_turn_on(self):
        """Turn on the switch."""
        await self._client.async_max_charge(True)

        # Not very graceful but wait here to avoid the mode coming back as 'CALCULATING'
        # It would be nice to simply ignore this state in future and try again after x seconds.
        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_turn_off(self):
        """Stop max charging.

        We are not changing anything, just applying the last rule. No need to supply anything.
        """
        await self._client.async_max_charge(False)

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()


class OhmeConfigurationSwitch(OhmeEntity, SwitchEntity):
    """Switch for changing configuration options."""

    def __init__(
        self,
        coordinator,
        hass: HomeAssistant,
        client,
        translation_key,
        icon,
        config_key,
    ) -> None:
        """Initialise switch."""
        self._attr_icon = f"mdi:{icon}"
        self._attr_translation_key = translation_key
        self._config_key = config_key
        self.legacy_id = config_key

        super().__init__(coordinator, hass, client)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Determine configuration value."""
        if self.coordinator.data is None:
            self._attr_is_on = None
        else:
            settings = self.coordinator.data["chargeDevices"][0]["optionalSettings"]
            self._attr_is_on = bool(settings[self._config_key])

        self._last_updated = utcnow()

        self.async_write_ha_state()

    async def async_turn_on(self):
        """Turn on the switch."""
        await self._client.async_set_configuration_value({self._config_key: True})

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_turn_off(self):
        """Turn off the switch."""
        await self._client.async_set_configuration_value({self._config_key: False})

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()


class OhmeSolarBoostSwitch(OhmeEntity, SwitchEntity):
    """Switch for changing configuration options."""

    _attr_translation_key = "solar_mode"
    _attr_icon = "mdi:solar-power"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Determine configuration value."""
        if self.coordinator.data is None:
            self._attr_is_on = None
        else:
            settings = self.coordinator.data["chargeDevices"][0]["optionalSettings"]
            self._attr_is_on = bool(settings["solarMode"] == "ZERO_EXPORT")

        self._last_updated = utcnow()

        self.async_write_ha_state()

    async def async_turn_on(self):
        """Turn on the switch."""
        await self._client.async_set_configuration_value({"solarMode": "ZERO_EXPORT"})

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_turn_off(self):
        """Turn off the switch."""
        await self._client.async_set_configuration_value({"solarMode": "IGNORE"})

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()


class OhmePriceCapSwitch(OhmeEntity, SwitchEntity):
    """Switch for enabling price cap."""

    _attr_translation_key = "enable_price_cap"
    _attr_icon = "mdi:car-speed-limiter"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Determine configuration value."""
        if self.coordinator.data is None:
            self._attr_is_on = None
        else:
            self._attr_is_on = bool(
                self.coordinator.data["userSettings"]["chargeSettings"][0]["enabled"]
            )

        self._last_updated = utcnow()

        self.async_write_ha_state()

    async def async_turn_on(self):
        """Turn on the switch."""
        await self._client.async_change_price_cap(enabled=True)

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()

    async def async_turn_off(self):
        """Turn off the switch."""
        await self._client.async_change_price_cap(enabled=False)

        await asyncio.sleep(1)
        await self.coordinator.async_refresh()
