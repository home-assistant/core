import logging
from typing import Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .device import ConnectionStatus, HIVIDevice
from .device_manager import HIVIDeviceManager

_LOGGER = logging.getLogger(__name__)


class HIVISlaveControlSwitchHub:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.switches = {}

    def get_switch(self, unique_id: str):
        return self.switches.get(unique_id)

    def add_switch(self, switch):
        self.switches[switch.unique_id] = switch


class HIVISlaveControlSwitch(SwitchEntity):
    """Control whether other speakers are set as slave speakers of the current speaker"""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: HIVISlaveControlSwitchHub,
        master_speaker_device_id: str,
        slave_speaker_device_id: str,
        device_manager: HIVIDeviceManager,
        create_type: str = "standalone",
    ):
        """Initialize

        Args:
            master_device: Master speaker device
            slave_device: Slave speaker device
            device_manager: Device manager
        """
        self.hass = hass
        self._hub = hub
        self._master_speaker_device_id = master_speaker_device_id
        self._slave_speaker_device_id = slave_speaker_device_id
        self._device_manager = device_manager

        self._slave_device_friendly_name = self.get_slave_device_friendly_name(
            create_type
        )
        # Entity attributes
        self._attr_name = f"{self._slave_device_friendly_name} Play in sync"
        self._attr_unique_id = (
            f"{master_speaker_device_id}_slave_{slave_speaker_device_id}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, master_speaker_device_id)},
        }
        self._attr_entity_category = EntityCategory.CONFIG

        self._hub.add_switch(self)

        # Store slave's ha_device_id at init to avoid race: DeviceDataRegistry also
        # listens to device_registry_updated and may pop the device before we look up.
        self._slave_ha_device_id: str | None = (
            self._device_manager.device_data_registry.get_ha_device_id_by_speaker_device_id(
                self._slave_speaker_device_id
            )
        )

        async def device_registry_updated(event):
            _LOGGER.debug("Device registry updated event: %s", event.data)
            ha_device_id = event.data["device_id"]
            action = event.data["action"]
            if action == "remove" and ha_device_id == self._slave_ha_device_id:
                _LOGGER.debug(
                    "Removing switch entity for deleted slave device %s",
                    self._slave_speaker_device_id,
                )
                self._hub.switches.pop(self._attr_unique_id, None)
                if self.hass and hasattr(self, "async_remove"):
                    await self.async_remove()

        self._unsub_device_registry = self.hass.bus.async_listen(
            "device_registry_updated", device_registry_updated
        )

    def get_master_device(self):
        """Get master and slave device objects"""
        master_device_dict = self._device_manager.device_data_registry.get_device_dict_by_speaker_device_id(
            self._master_speaker_device_id
        )
        if master_device_dict is None:
            _LOGGER.warning(
                f"Cannot find master device {self._master_speaker_device_id}"
            )
            return None

        master_device = HIVIDevice(**master_device_dict)

        return master_device

    def get_slave_device_friendly_name(self, create_type: str) -> str:
        """Get friendly name of slave device"""
        master_device = self.get_master_device()
        slave_device_friendly_name = ""
        if create_type == "from_standalone_device":
            slave_device_dict = self._device_manager.device_data_registry.get_device_dict_by_speaker_device_id(
                self._slave_speaker_device_id
            )
            if slave_device_dict is not None:
                slave_device = HIVIDevice(**slave_device_dict)
                slave_device_friendly_name = slave_device.friendly_name
            else:
                _LOGGER.error(
                    f"Cannot find information for slave device {self._slave_speaker_device_id}"
                )

        elif create_type == "from_slave_device":
            slave_device_list = master_device.slave_device_list
            for device_info in slave_device_list:
                if device_info.uuid == self._slave_speaker_device_id:
                    slave_device_friendly_name = device_info.friendly_name
                    break
            else:
                _LOGGER.error(
                    f"Cannot find information for slave device {self._slave_speaker_device_id} in the slave device list of master device {master_device.friendly_name}"
                )

        return slave_device_friendly_name

    def get_slave_device_ip_addr_by_standalone(self) -> str:
        """Get IP address of slave device"""
        slave_device_ip_addr = None

        slave_device_dict = self._device_manager.device_data_registry.get_device_dict_by_speaker_device_id(
            self._slave_speaker_device_id
        )
        if slave_device_dict is not None:
            slave_device = HIVIDevice(**slave_device_dict)
            slave_device_ip_addr = slave_device.ip_addr
        else:
            _LOGGER.error(
                f"Cannot find information for slave device {self._slave_speaker_device_id}"
            )

        return slave_device_ip_addr

    def get_slave_device_ip_addr_by_slave(self) -> str:
        """Get IP address of slave device"""
        slave_device_ip_addr = None

        master_device = self.get_master_device()
        if master_device is None:
            _LOGGER.error(
                "Master device %s not found, cannot get slave IP",
                self._master_speaker_device_id,
            )
            return None
        slave_device_list = master_device.slave_device_list
        if slave_device_list is None:
            _LOGGER.error(
                f"Slave device list of master device {master_device.friendly_name} is empty"
            )
            return None
        for device_info in slave_device_list:
            if device_info.uuid == self._slave_speaker_device_id:
                slave_device_ip_addr = device_info.ip_addr
                break
        else:
            _LOGGER.error(
                f"Cannot find information for slave device {self._slave_speaker_device_id} in the slave device list of master device {master_device.friendly_name}"
            )

        return slave_device_ip_addr

    async def async_added_to_hass(self):
        """When entity is added to hass"""
        _LOGGER.debug("Adding switch entity %s to Home Assistant", self.name)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from device_registry_updated when entity is removed."""
        if self._unsub_device_registry is not None:
            self._unsub_device_registry()
            self._unsub_device_registry = None

    @property
    def available(self) -> bool:
        """Whether the switch is available."""
        master_device = self.get_master_device()
        if master_device is None:
            return False
        return (
            master_device.connection_status == ConnectionStatus.ONLINE
            and master_device.can_be_master
        )

    def on_off_switch(self, is_on: bool):
        """Enable or disable the switch

        Args:
            is_on: True for on, False for off
        """
        if self._attr_is_on != is_on:
            self._attr_is_on = is_on
            # Notify Home Assistant to update state
            if self.hass and hasattr(self, "async_write_ha_state"):
                self.async_write_ha_state()

            _LOGGER.debug(
                "Switch %s state set to: %s", self._attr_name, "ON" if is_on else "OFF"
            )

    async def async_turn_on(self, **kwargs):
        """Turn on the switch - set master-slave relationship"""
        master_device = self.get_master_device()
        if master_device is None:
            _LOGGER.error(
                "Master device %s not found, cannot turn on",
                self._master_speaker_device_id,
            )
            return
        _LOGGER.debug(
            "Setting device %s as slave of device %s",
            self._slave_device_friendly_name,
            master_device.friendly_name,
        )
        self._attr_is_on = True

        async def operation_callback(result: Dict):
            """Operation callback function"""
            _LOGGER.debug("sync_group_operation turn on result: %s", result)
            need_refresh_flg = False
            if result.get("status") in [
                "rejected",
            ]:
                self._attr_is_on = False
            elif result.get("status") in [
                "accepted",
            ]:
                await self.hass.services.async_call(
                    DOMAIN, "postpone_discovery", {}, blocking=False
                )
            elif result.get("status") in [
                "executing",
                "verifying",
            ]:
                pass
            elif result.get("status") in ["success"]:
                need_refresh_flg = True
                _LOGGER.debug("need to refresh, status: %s", result.get("status"))
            elif result.get("status") in [
                "execution_failed",
                "error",
                "timeout",
                "max_retries_exceeded",
                "cancelled",
                "polling_error",
            ]:
                self._attr_is_on = False
                need_refresh_flg = True
                _LOGGER.debug("need to refresh, status: %s", result.get("status"))

            if need_refresh_flg:
                await self.hass.services.async_call(
                    DOMAIN, "refresh_discovery", {}, blocking=False
                )

            self.async_write_ha_state()

        slave_device_ip_addr = self.get_slave_device_ip_addr_by_standalone()
        if slave_device_ip_addr is None:
            _LOGGER.error(
                "Cannot find IP address of slave device %s, failed to set master-slave relationship",
                self._slave_device_friendly_name,
            )
            self._attr_is_on = False
            self.async_write_ha_state()
            return

        master_device = self.get_master_device()
        if master_device is None:
            _LOGGER.error(
                "Master device %s not found, cannot prepare operation",
                self._master_speaker_device_id,
            )
            self._attr_is_on = False
            self.async_write_ha_state()
            return

        # Prepare operation data
        slave_ip = slave_device_ip_addr
        ssid = master_device.ssid
        wifi_channel = master_device.wifi_channel
        auth = master_device.auth_mode
        encry = master_device.encryption_mode
        psk = master_device.psk
        master_ip = master_device.ip_addr
        uuid = master_device.uuid
        operation_data = {
            "type": "set_slave",
            "master": self._master_speaker_device_id,
            "slave": self._slave_speaker_device_id,
            "expected_state": "slave",
            "params": {
                "slave_ip": slave_ip,
                "ssid": ssid,
                "wifi_channel": wifi_channel,
                "auth": auth,
                "encry": encry,
                "psk": psk,
                "master_ip": master_ip,
                "uuid": uuid,
            },
        }

        # Send request via dispatcher (requires corresponding receiver support)
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_sync_group_operation",
            operation_data,
            operation_callback,  # Pass callback function
        )

    async def async_turn_off(self, **kwargs):
        """Turn off the switch - remove master-slave relationship"""
        master_device = self.get_master_device()
        if master_device is None:
            _LOGGER.error(
                "Master device %s not found, cannot turn off",
                self._master_speaker_device_id,
            )
            return
        self._attr_is_on = False

        _LOGGER.debug(
            "Removing device %s as slave of device %s",
            self._slave_device_friendly_name,
            master_device.friendly_name,
        )

        async def operation_callback(result: Dict):
            """Operation callback function"""
            _LOGGER.debug("sync_group_operation turn on result: %s", result)
            need_refresh_flg = False
            if result.get("status") in [
                "rejected",
            ]:
                self._attr_is_on = True
            elif result.get("status") in [
                "accepted",
            ]:
                await self.hass.services.async_call(
                    DOMAIN, "postpone_discovery", {}, blocking=False
                )
            elif result.get("status") in [
                "executing",
                "verifying",
            ]:
                # _LOGGER.debug(
                #     "no need to refresh yet, status: %s", result.get("status")
                # )
                pass
            elif result.get("status") in [
                "execution_failed",
                "error",
                "timeout",
                "max_retries_exceeded",
                "success",
                "cancelled",
                "polling_error",
            ]:
                need_refresh_flg = True
                _LOGGER.debug("need to refresh, status: %s", result.get("status"))

            if need_refresh_flg:
                await self.hass.services.async_call(
                    DOMAIN, "refresh_discovery", {}, blocking=False
                )

            self.async_write_ha_state()

        slave_ip_ra0 = self.get_slave_device_ip_addr_by_slave()

        if slave_ip_ra0 is None:
            _LOGGER.error(
                "Cannot find IP address of slave device %s, failed to remove master-slave relationship",
                self._slave_device_friendly_name,
            )
            self._attr_is_on = True
            self.async_write_ha_state()
            return
        operation_data = {
            "type": "remove_slave",
            "master": self._master_speaker_device_id,
            "slave": self._slave_speaker_device_id,
            "expected_state": "standalone",
            "params": {
                "master_ip": master_device.ip_addr,
                "slave_ip_ra0": slave_ip_ra0,
            },
        }

        # Send request via dispatcher (requires corresponding receiver support)
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_sync_group_operation",
            operation_data,
            operation_callback,  # Pass callback function
        )

    @property
    def extra_state_attributes(self):
        """Extra state attributes"""
        master_device = self.get_master_device()
        return {
            "master_device": master_device.speaker_device_id if master_device else None,
            "slave_device": self._slave_speaker_device_id,
            "master_name": master_device.friendly_name if master_device else None,
            "slave_name": self._slave_device_friendly_name,
        }


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switch entities."""
    device_manager = hass.data[DOMAIN][config_entry.entry_id]["device_manager"]
    device_manager.set_add_entities_callback("switch", async_add_entities)
