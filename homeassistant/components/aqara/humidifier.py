"""Support for Aqara (de)humidifiers."""
from __future__ import annotations

from dataclasses import dataclass

from aqara_iot import AqaraDeviceManager, AqaraPoint

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantAqaraData
from .base import (  # EnumTypeData,; IntegerTypeData,
    AqaraEntity,
    find_aqara_device_points_and_register,
)
from .const import AQARA_DISCOVERY_NEW, DOMAIN


@dataclass
class AqaraHumidifierEntityDescription(HumidifierEntityDescription):
    """Describe an Aqara (de)humidifier entity."""

    water_level_res_id: str | None = ""  # Water Level
    relative_humidity_res_id: str | None = ""  # Environment Relative Hum
    environment_temperature_res_id: str | None = ""  # Environment Temperat
    fan_level_res_id: str | None = ""  # Humidifier Fan Level
    switch_status_res_id: str | None = ""  # Humidifier Switch Status
    alarm_switch_status_res_id: str | None = ""  # Alarm
    locked_switch_status_res_id: str | None = ""  # Physical Control Locked
    supported_features: int = 0


zhimi_humidifier = AqaraHumidifierEntityDescription(
    key="4.1.85",
    water_level_res_id="13.1.85",  # Water Level
    relative_humidity_res_id="13.2.85",  # Environment Relative Hum
    environment_temperature_res_id="13.3.85",  # Environment Temperat
    fan_level_res_id="14.1.85",  # Humidifier Fan Level
    switch_status_res_id="4.1.85",  # Humidifier Switch Status
    alarm_switch_status_res_id="4.3.85",  # Alarm
    locked_switch_status_res_id="4.4.85",  # Physical Control Locked
    #########################################
    device_class=HumidifierDeviceClass.HUMIDIFIER,
)


HUMIDIFIERS: dict[str, AqaraHumidifierEntityDescription] = {
    # # Humidifier
    "miot.humidifier.cb1": zhimi_humidifier,  # 智米纯净型加湿器,
    "miot.humidifier.ca1": zhimi_humidifier,  # 智米纯净型加湿
    "miot.humidifier.v1": zhimi_humidifier,  # 智米除菌加湿器器
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aqara (de)humidifier dynamically through Aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Aqara (de)humidifier."""
        entities: list[AqaraHumidifierEntity] = []

        def append_entity(aqara_point, description):
            entities.append(
                AqaraHumidifierEntity(
                    aqara_point, hass_data.device_manager, description
                )
            )

        find_aqara_device_points_and_register(
            hass, entry.entry_id, hass_data, device_ids, HUMIDIFIERS, append_entity
        )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )


class AqaraHumidifierEntity(AqaraEntity, HumidifierEntity):
    """Aqara (de)humidifier Device."""

    # _set_humidity_type: IntegerTypeData
    entity_description: AqaraHumidifierEntityDescription
    _supported_features = 0

    def __init__(
        self,
        device: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraHumidifierEntityDescription,
    ) -> None:
        """Init Aqara (de)humidier."""
        super().__init__(device, device_manager)
        self.entity_description = description
        # self._attr_available_modes: list[str] = []

    @property
    def is_on(self) -> bool:
        """Return the device is on or off."""
        value = self.device_manager.get_point_value(
            self.point.did, self.entity_description.switch_status_res_id
        )

        return value in ("1", "true")

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        return None

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        value = self.device_manager.get_point_value(
            self.point.did, self.entity_description.relative_humidity_res_id
        )
        if value is None or value == "":
            return None

        return round(float(value))

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command([{self.entity_description.switch_status_res_id: "1"}])

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command([{self.entity_description.switch_status_res_id: "0"}])

    def set_humidity(self, humidity):
        """Set new target humidity."""
        self._send_command(
            [{self.entity_description.relative_humidity_res_id: humidity}]
        )

    def set_mode(self, mode):
        """Set new target preset mode."""
        # self._send_command([{self.point.resource_id, str(mode)}])
