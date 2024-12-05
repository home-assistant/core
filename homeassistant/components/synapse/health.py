from .const import DOMAIN

from homeassistant.core import callback, HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.binary_sensor import BinarySensorEntity
import logging
from .const import SynapseApplication


class SynapseHealthSensor(BinarySensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        namespace: str,
        device,
        config_entry: ConfigEntry,
    ):
        self.config_entry = config_entry
        self.config_data: SynapseApplication = config_entry.data
        self.device = device
        self.namespace = namespace
        self.hass = hass
        self._heartbeat_timer = None
        self.logger = logging.getLogger(__name__)
        self.online = False
        self._listen()

    @property
    def device_info(self) -> DeviceInfo:
        return self.device

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        return f"{self.config_data.get("title")} Online"

    @property
    def unique_id(self):
        return f"{self.config_data.get("unique_id")}-online"

    @property
    def is_on(self):
        return self.online

    def _listen(self):
        self.async_on_remove(
          self.hass.bus.async_listen(
              self.event_name("heartbeat"),
              self._handle_heartbeat
          )
        )
        self.async_on_remove(
          self.hass.bus.async_listen(
              self.event_name("shutdown"),
              self._handle_shutdown
          )
        )
        self._reset_heartbeat_timer()

    @callback
    def _handle_shutdown(self, event):
        """Explicit shutdown events emitted by app"""
        self.logger.debug(f"{self.config_data.get("app")} going offline")
        self.online = False
        self.hass.bus.async_fire(self.event_name("health"))
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        self.async_schedule_update_ha_state(True)

    @callback
    def _mark_as_dead(self, event=None):
        """Timeout on heartbeat. Unexpected shutdown by app?"""
        if self.online == False:
            return
        # He's dead Jim
        self.logger.info(f"{self.config_data.get("app")} no heartbeat")
        self.online = False
        self.hass.bus.async_fire(self.event_name("health"))
        self.async_schedule_update_ha_state(True)

    def _reset_heartbeat_timer(self):
        """Detected a heartbeat, wait for next"""
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        self._heartbeat_timer = self.hass.loop.call_later(30, self._mark_as_dead)
        self.async_on_remove(lambda: self._heartbeat_timer.cancel())
    @callback
    def _handle_heartbeat(self, event):
        """Handle heartbeat events."""
        self._reset_heartbeat_timer()
        if self.online == True:
            return
        self.logger.debug(f"{self.config_data.get("app")} online")
        self.online = True
        self.hass.bus.async_fire(self.event_name("health"))
        self.async_schedule_update_ha_state(True)

    def event_name(self, event: str):
        """Standard format for event bus names to keep apps separate"""
        return f"{self.namespace}/{event}/{self.config_data.get("app")}"
