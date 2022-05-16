from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import *
from homeassistant.const import TEMP_CELSIUS

from .core.const import DOMAIN
from .core.entity import XEntity
from .core.ewelink import XRegistry, SIGNAL_ADD_ENTITIES

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]
    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES,
        lambda x: add_entities([e for e in x if isinstance(e, ClimateEntity)])
    )


# noinspection PyAbstractClass
class XClimateTH(XEntity, ClimateEntity):
    params = {"targets", "deviceType", "currentTemperature", "temperature"}

    _attr_entity_registry_enabled_default = False
    _attr_hvac_mode = None
    _attr_hvac_modes = [
        HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_DRY
    ]
    _attr_max_temp = 99
    _attr_min_temp = 1
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE_RANGE
    _attr_target_temperature_high = None
    _attr_target_temperature_low = None
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_target_temperature_step = 1

    heat: bool = None

    def set_state(self, params: dict):
        if "targets" in params:
            hi, lo = params["targets"]

            self._attr_is_aux_heat = lo["reaction"]["switch"] == "on"
            self._attr_target_temperature_high = float(hi["targetHigh"])
            self._attr_target_temperature_low = float(lo["targetLow"])

            if params["deviceType"] == "normal":
                self._attr_hvac_mode = HVAC_MODE_OFF
            elif params["deviceType"] == "humidity":
                self._attr_hvac_mode = HVAC_MODE_DRY
            elif self.is_aux_heat:
                self._attr_hvac_mode = HVAC_MODE_HEAT
            else:
                self._attr_hvac_mode = HVAC_MODE_COOL

        try:
            if self.hvac_mode != HVAC_MODE_DRY:
                value = float(
                    params.get("currentTemperature") or params["temperature"]
                )
                value = round(value, 1)
            else:
                value = int(
                    params.get("currentHumidity") or params["humidity"]
                )
            self._attr_current_temperature = value
        except Exception:
            pass

    def get_targets(self, heat: bool) -> list:
        return [{
            "targetHigh": str(self.target_temperature_high),
            "reaction": {"switch": "off" if heat else "on"}
        }, {
            "targetLow": str(self.target_temperature_low),
            "reaction": {"switch": "on" if heat else "off"}
        }]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        if hvac_mode == HVAC_MODE_HEAT:
            params = {
                "mainSwitch": "on", "deviceType": "temperature",
                "targets": self.get_targets(True)
            }
        elif hvac_mode == HVAC_MODE_COOL:
            params = {
                "mainSwitch": "on", "deviceType": "temperature",
                "targets": self.get_targets(False)
            }
        elif hvac_mode == HVAC_MODE_DRY:
            params = {
                "mainSwitch": "on", "deviceType": "humidity",
                "targets": self.get_targets(self.is_aux_heat)
            }
        else:
            params = {"mainSwitch": "off", "deviceType": "normal"}
        await self.ewelink.cloud.send(self.device, params)

    async def async_set_temperature(
            self, hvac_mode: str = None, target_temp_high: float = None,
            target_temp_low: float = None, **kwargs
    ) -> None:
        heat = self.is_aux_heat
        if hvac_mode is None:
            params = {}
        elif hvac_mode == HVAC_MODE_HEAT:
            heat = True
            params = {"mainSwitch": "on", "deviceType": "temperature"}
        elif hvac_mode == HVAC_MODE_COOL:
            heat = False
            params = {"mainSwitch": "on", "deviceType": "temperature"}
        elif hvac_mode == HVAC_MODE_DRY:
            params = {"mainSwitch": "on", "deviceType": "humidity"}
        else:
            params = {"mainSwitch": "off", "deviceType": "normal"}

        if target_temp_high is not None and target_temp_low is not None:
            params["targets"] = [{
                "targetHigh": str(target_temp_high),
                "reaction": {"switch": "off" if heat else "on"}
            }, {
                "targetLow": str(target_temp_low),
                "reaction": {"switch": "on" if heat else "off"}
            }]

        await self.ewelink.cloud.send(self.device, params)


# noinspection PyAbstractClass
class XClimateNS(XEntity, ClimateEntity):
    params = {"ATCEnable", "ATCMode", "temperature", "tempCorrection"}

    _attr_entity_registry_enabled_default = False
    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO]
    _attr_max_temp = 31
    _attr_min_temp = 16
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_target_temperature_step = 1

    def set_state(self, params: dict):
        cache = self.device["params"]
        if cache != params:
            cache.update(params)

        if "HMI_ATCDevice" in params and "etype" in params["HMI_ATCDevice"]:
            self._attr_hvac_modes[1] = HVAC_MODE_COOL \
                if cache["HMI_ATCDevice"]["etype"] == "cold" \
                else HVAC_MODE_HEAT

        if "ATCEnable" in params or "ATCMode" in params:
            if cache["ATCEnable"]:
                if cache["ATCMode"]:
                    self._attr_hvac_mode = HVAC_MODE_AUTO
                    self._attr_supported_features = 0
                else:
                    self._attr_hvac_mode = self.hvac_modes[1]
                    self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
            else:
                self._attr_hvac_mode = HVAC_MODE_OFF
                self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE

        if "ATCExpect0" in params:
            self._attr_target_temperature = cache["ATCExpect0"]

        # correction could be optional
        # https://github.com/AlexxIT/SonoffLAN/issues/812
        if "temperature" in params or "tempCorrection" in params:
            self._attr_current_temperature = \
                cache["temperature"] + cache.get("tempCorrection", 0)

    @staticmethod
    def get_params(hvac_mode: str) -> dict:
        if hvac_mode == HVAC_MODE_AUTO:
            return {"ATCEnable": 1, "ATCMode": 1}
        elif hvac_mode in (HVAC_MODE_HEAT_COOL, HVAC_MODE_HEAT):
            return {"ATCEnable": 1, "ATCMode": 0}
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            return {"ATCEnable": 1}  # async_turn_on
        elif hvac_mode == HVAC_MODE_OFF:
            return {"ATCEnable": 0}
        else:
            return {}

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        params = self.get_params(hvac_mode)
        await self.ewelink.cloud.send(self.device, params)

    async def async_set_temperature(
            self, temperature: float = None, hvac_mode: str = None, **kwargs
    ) -> None:
        params = self.get_params(hvac_mode)
        if temperature is not None:
            params["ATCExpect0"] = temperature
        if not params:
            params["ATCEnable"] = 1
        await self.ewelink.cloud.send(self.device, params)


# noinspection PyAbstractClass
class XThermostat(XEntity, ClimateEntity):
    params = {"switch", "targetTemp", "temperature", "workMode", "workState"}

    # @bwp91 https://github.com/AlexxIT/SonoffLAN/issues/358
    _attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_AUTO]
    _attr_max_temp = 45
    _attr_min_temp = 5
    _attr_preset_modes = ["manual", "programmed", "economical"]
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_target_temperature_step = 0.5

    def set_state(self, params: dict):
        cache = self.device["params"]
        if cache != params:
            cache.update(params)

        if cache["switch"] == "on":
            # workState: 1=heating, 2=auto
            self._attr_hvac_mode = self.hvac_modes[cache["workState"]]
        else:
            self._attr_hvac_mode = HVAC_MODE_OFF

        if "workMode" in params:
            self._attr_preset_mode = self.preset_modes[params["workMode"] - 1]

        if "targetTemp" in params:
            self._attr_target_temperature = params["targetTemp"]
        if "temperature" in params:
            self._attr_current_temperature = params["temperature"]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        i = self.hvac_modes.index(hvac_mode)
        params = {"switch": "on", "workState": i} if i else {"switch": "off"}
        await self.ewelink.send(self.device, params)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        i = self.preset_modes.index(preset_mode) + 1
        await self.ewelink.send(self.device, {"workMode": i})

    async def async_set_temperature(
            self, temperature: float = None, hvac_mode: str = None,
            preset_mode: str = None, **kwargs
    ) -> None:
        if hvac_mode is None:
            params = {}
        elif hvac_mode is HVAC_MODE_OFF:
            params = {"switch": "off"}
        else:
            i = self.hvac_modes.index(hvac_mode)
            params = {"switch": "on", "workState": i}

        if preset_mode is not None:
            params["workMode"] = self.preset_modes.index(preset_mode) + 1

        if temperature is not None:
            params["targetTemp"] = temperature

        await self.ewelink.send(self.device, params)
