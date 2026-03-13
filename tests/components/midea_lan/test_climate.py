"""Tests for midea_lan climate.py."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.c3.const import DeviceAttributes as C3Attributes
from midealocal.devices.cc import DeviceAttributes as CCAttributes
from midealocal.devices.cf import DeviceAttributes as CFAttributes
from midealocal.devices.fb import DeviceAttributes as FBAttributes

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SWING_BOTH,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    HVACMode,
)
from homeassistant.components.midea_lan import climate
from homeassistant.components.midea_lan.const import DEVICES, DOMAIN
from homeassistant.const import ATTR_TEMPERATURE, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant


class DummyDevice:
    """Simple fake Midea device for climate tests."""

    def __init__(
        self,
        device_type: int,
        *,
        attributes: dict | None = None,
    ) -> None:
        """Initialize fake device."""
        self.device_type = device_type
        self.device_id = 123
        self.name = "Dummy"
        self.model = "M1"
        self.subtype = 7
        self.available = True
        self.attributes = attributes or {}
        self._callbacks: list[Callable] = []
        self.calls: list[tuple] = []
        self.temperature_step = 1
        self.fan_modes = ["low", "high"]
        self.modes = ["comfort", "eco"]

    def register_update(self, callback: Callable) -> None:
        """Record update callback registration."""
        self._callbacks.append(callback)

    def get_attribute(self, attr):
        """Return attribute value."""
        return self.attributes.get(attr)

    def set_attribute(self, attr, value) -> None:
        """Record set attribute call."""
        self.calls.append(("set_attribute", attr, value))

    def set_target_temperature(self, **kwargs) -> None:
        """Record set target temperature call."""
        self.calls.append(("set_target_temperature", kwargs))

    def set_swing(self, **kwargs) -> None:
        """Record set swing call."""
        self.calls.append(("set_swing", kwargs))

    def set_mode(self, zone: int, mode: int) -> None:
        """Record set mode call."""
        self.calls.append(("set_mode", zone, mode))


def _climate_entities() -> list[climate.MideaClimateEntityDescription]:
    """Return minimal CLIMATE_ENTITIES list used by climate tests."""
    return [
        climate.MideaClimateEntityDescription(
            key="named",
            model=[DeviceType.AC],
            translation_key="named",
        ),
        climate.MideaClimateEntityDescription(
            key="extra",
            model=[DeviceType.AC],
            translation_key="extra",
            entity_registry_enabled_default=False,
        ),
        climate.MideaClimateEntityDescription(
            key="named",
            model=[DeviceType.CC],
            translation_key="named",
        ),
        climate.MideaClimateEntityDescription(
            key="named",
            model=[DeviceType.CF],
            translation_key="named",
        ),
        climate.MideaClimateEntityDescription(
            key="named",
            model=[DeviceType.C3],
            translation_key="named",
            zone=0,
        ),
        climate.MideaClimateEntityDescription(
            key="named",
            model=[DeviceType.FB],
            translation_key="named",
        ),
    ]


def _get_description(
    device_type: int,
    entity_key: str,
) -> climate.MideaClimateEntityDescription:
    """Return one climate description for a device type and entity key."""
    return {
        entity.key: entity
        for entity in _climate_entities()
        if device_type in entity.model
    }[entity_key]


def test_midea_climate_base_methods() -> None:
    """Test base climate behavior and setters."""
    attrs = {
        "power": True,
        "mode": 1,
        "target_temperature": 22.0,
        "indoor_temperature": 21.0,
        "comfort_mode": False,
        "eco_mode": False,
        "boost_mode": False,
        "sleep_mode": False,
        "frost_protect": False,
    }
    with patch.object(climate, "CLIMATE_ENTITIES", _climate_entities()):
        dev = DummyDevice(DeviceType.AC, attributes=attrs)
        ent = climate.MideaACClimate(
            dev,
            _get_description(DeviceType.AC, "named"),
            MagicMock(options={"sensors": []}),
        )

    assert ent.supported_features
    assert ent._attr_name is None
    assert ent.hvac_mode == HVACMode.AUTO
    ent.device.attributes["power"] = False
    assert ent.hvac_mode == HVACMode.OFF
    ent.device.attributes["power"] = True
    assert ent.target_temperature == 22.0
    assert ent.current_temperature == 21.0
    assert ent.preset_mode == PRESET_NONE

    ent.device.attributes.update({"comfort_mode": True, "eco_mode": False})
    assert ent.preset_mode == PRESET_COMFORT
    ent.device.attributes.update({"comfort_mode": False, "eco_mode": True})
    assert ent.preset_mode == PRESET_ECO
    ent.device.attributes.update({"eco_mode": False, "boost_mode": True})
    assert ent.preset_mode == PRESET_BOOST
    ent.device.attributes.update({"boost_mode": False, "sleep_mode": True})
    assert ent.preset_mode == PRESET_SLEEP
    ent.device.attributes.update({"sleep_mode": False, "frost_protect": True})
    assert ent.preset_mode == PRESET_AWAY
    ent.device.attributes.update({"frost_protect": False})

    assert ent.extra_state_attributes == attrs

    ent.turn_on()
    ent.turn_off()
    assert ("set_attribute", "power", True) in dev.calls
    assert ("set_attribute", "power", False) in dev.calls

    ent.set_temperature()
    ent.set_temperature(**{ATTR_TEMPERATURE: 23.1, ATTR_HVAC_MODE: HVACMode.OFF})
    ent.set_temperature(**{ATTR_TEMPERATURE: 23.1, ATTR_HVAC_MODE: HVACMode.COOL})
    ent.set_temperature(**{ATTR_TEMPERATURE: 23.1, ATTR_HVAC_MODE: "invalid"})

    ent.set_hvac_mode(HVACMode.OFF)
    ent.set_hvac_mode(HVACMode.HEAT)

    for preset in (
        PRESET_AWAY,
        PRESET_COMFORT,
        PRESET_SLEEP,
        PRESET_ECO,
        PRESET_BOOST,
    ):
        ent.set_preset_mode(preset)

    for key, expected in (
        ("frost_protect", ("set_attribute", "frost_protect", False)),
        ("comfort_mode", ("set_attribute", "comfort_mode", False)),
        ("sleep_mode", ("set_attribute", "sleep_mode", False)),
        ("eco_mode", ("set_attribute", "eco_mode", False)),
        ("boost_mode", ("set_attribute", "boost_mode", False)),
    ):
        dev.attributes.update(
            {
                "frost_protect": False,
                "comfort_mode": False,
                "sleep_mode": False,
                "eco_mode": False,
                "boost_mode": False,
            }
        )
        dev.attributes[key] = True
        ent.set_preset_mode(PRESET_NONE)
        assert expected in dev.calls

    ent.schedule_update_ha_state = MagicMock()
    ent.hass = None
    ent.update_state({})
    ent.hass = MagicMock()
    ent.update_state({})
    ent.schedule_update_ha_state.assert_called_once()


def test_midea_ac_specific() -> None:
    """Test AC-specific properties and controls."""
    attrs = {
        ACAttributes.fan_speed: 103,
        ACAttributes.swing_vertical: True,
        ACAttributes.swing_horizontal: True,
        "indoor_humidity": 50,
        ACAttributes.outdoor_temperature: 10.5,
    }
    with patch.object(climate, "CLIMATE_ENTITIES", _climate_entities()):
        ent = climate.MideaACClimate(
            DummyDevice(DeviceType.AC, attributes=attrs),
            _get_description(DeviceType.AC, "named"),
            MagicMock(options={"sensors": ["indoor_humidity"]}),
        )
    assert ent.fan_mode == FAN_AUTO
    ent.device.attributes[ACAttributes.fan_speed] = 95
    assert ent.fan_mode == climate.FAN_FULL_SPEED
    ent.device.attributes[ACAttributes.fan_speed] = 70
    assert ent.fan_mode == FAN_HIGH
    ent.device.attributes[ACAttributes.fan_speed] = 50
    assert ent.fan_mode == FAN_MEDIUM
    ent.device.attributes[ACAttributes.fan_speed] = 30
    assert ent.fan_mode == FAN_LOW
    ent.device.attributes[ACAttributes.fan_speed] = 10
    assert ent.fan_mode == climate.FAN_SILENT

    assert ent.swing_mode == SWING_BOTH
    ent.device.temperature_step = 1
    assert ent.target_temperature_step == 1
    ent.device.temperature_step = 0
    assert ent.target_temperature_step == 0.5

    assert ent.current_humidity == 50.0
    ent.device.attributes["indoor_humidity"] = 255
    assert ent.current_humidity is None

    ent._indoor_humidity_enabled = False
    assert ent.current_humidity is None

    assert ent.outdoor_temperature == 10.5
    ent.set_fan_mode(FAN_LOW)
    ent.set_fan_mode("unknown")
    ent.set_swing_mode(SWING_VERTICAL)


def test_midea_cc_specific() -> None:
    """Test CC-specific properties and controls."""
    attrs = {
        CCAttributes.fan_speed: "high",
        CCAttributes.temperature_precision: 0.5,
        CCAttributes.swing: True,
    }
    with patch.object(climate, "CLIMATE_ENTITIES", _climate_entities()):
        ent = climate.MideaCCClimate(
            DummyDevice(DeviceType.CC, attributes=attrs),
            _get_description(DeviceType.CC, "named"),
        )
    assert ent.fan_modes == ["low", "high"]
    assert ent.fan_mode == "high"
    assert ent.target_temperature_step == 0.5
    assert ent.swing_mode == SWING_ON
    ent.device.attributes[CCAttributes.swing] = False
    assert ent.swing_mode == SWING_OFF
    ent.set_fan_mode("low")
    ent.set_swing_mode(SWING_ON)


def test_midea_cf_specific() -> None:
    """Test CF-specific properties."""
    attrs = {
        CFAttributes.min_temperature: 16,
        CFAttributes.max_temperature: 30,
        CFAttributes.current_temperature: 22,
    }
    with patch.object(climate, "CLIMATE_ENTITIES", _climate_entities()):
        ent = climate.MideaCFClimate(
            DummyDevice(DeviceType.CF, attributes=attrs),
            _get_description(DeviceType.CF, "named"),
        )
    assert ent.supported_features
    assert ent.min_temp == 16
    assert ent.max_temp == 30
    assert ent.target_temperature_low == 16
    assert ent.target_temperature_high == 30
    assert ent.current_temperature == 22


def test_midea_c3_specific() -> None:
    """Test C3-specific properties and controls."""
    attrs = {
        C3Attributes.zone_temp_type: [True, False],
        C3Attributes.temperature_min: [16, 17],
        C3Attributes.temperature_max: [30, 29],
        C3Attributes.mode: 1,
        C3Attributes.zone1_power: True,
        C3Attributes.target_temperature: [22, 23],
    }
    with patch.object(climate, "CLIMATE_ENTITIES", _climate_entities()):
        description = _get_description(DeviceType.C3, "named")
        ent = climate.MideaC3Climate(
            DummyDevice(DeviceType.C3, attributes=attrs),
            description,
            0,
        )

    assert ent.supported_features
    assert ent.target_temperature_step == 1
    ent.device.attributes[C3Attributes.zone_temp_type] = [False, False]
    assert ent.target_temperature_step == 0.5
    assert ent.min_temp == 16
    assert ent.max_temp == 30
    assert ent.target_temperature_low == 16
    assert ent.target_temperature_high == 30
    assert ent.hvac_mode == HVACMode.AUTO
    ent.device.attributes[C3Attributes.mode] = "bad"
    assert ent.hvac_mode == HVACMode.OFF
    assert ent.target_temperature == 22
    assert ent.current_temperature is None

    ent.turn_on()
    ent.turn_off()
    ent.set_temperature()
    ent.set_temperature(**{ATTR_TEMPERATURE: 21.4, ATTR_HVAC_MODE: HVACMode.OFF})
    ent.set_temperature(**{ATTR_TEMPERATURE: 21.4, ATTR_HVAC_MODE: HVACMode.COOL})
    ent.set_temperature(**{ATTR_TEMPERATURE: 21.4, ATTR_HVAC_MODE: "invalid"})
    ent.set_hvac_mode(HVACMode.OFF)
    ent.set_hvac_mode(HVACMode.HEAT)


def test_midea_fb_specific() -> None:
    """Test FB-specific properties and controls."""
    attrs = {
        FBAttributes.mode: "comfort",
        FBAttributes.power: True,
        FBAttributes.current_temperature: 20,
    }
    with patch.object(climate, "CLIMATE_ENTITIES", _climate_entities()):
        ent = climate.MideaFBClimate(
            DummyDevice(DeviceType.FB, attributes=attrs),
            _get_description(DeviceType.FB, "named"),
        )
    assert ent.supported_features
    assert ent.preset_mode == "comfort"
    assert ent.hvac_mode == HVACMode.HEAT
    ent.device.attributes[FBAttributes.power] = False
    assert ent.hvac_mode == HVACMode.OFF
    assert ent.current_temperature == 20

    ent.set_temperature()
    ent.set_temperature(**{ATTR_TEMPERATURE: 24.2, ATTR_HVAC_MODE: HVACMode.OFF})
    ent.set_temperature(**{ATTR_TEMPERATURE: 24.2, ATTR_HVAC_MODE: HVACMode.HEAT})
    ent.set_hvac_mode(HVACMode.OFF)
    ent.set_hvac_mode(HVACMode.HEAT)
    ent.set_preset_mode("eco")


async def test_climate_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry creates entities for each supported device type."""
    add_entities = MagicMock()
    config_entry = MagicMock(data={CONF_DEVICE_ID: 123}, options={})

    with patch.object(climate, "CLIMATE_ENTITIES", _climate_entities()):
        hass.data[DOMAIN] = {DEVICES: {123: DummyDevice(DeviceType.AC)}}

        # Ensure optional entities (default=False) are skipped unless explicitly enabled.
        with patch.object(
            climate, "MideaACClimate", side_effect=lambda *_: "ac"
        ) as ac_ctor:
            await climate.async_setup_entry(hass, config_entry, add_entities)
        assert ac_ctor.call_count == 2

        with (
            patch.object(climate, "MideaACClimate", side_effect=lambda *_: "ac"),
            patch.object(climate, "MideaCCClimate", side_effect=lambda *_: "cc"),
            patch.object(climate, "MideaCFClimate", side_effect=lambda *_: "cf"),
            patch.object(climate, "MideaC3Climate", side_effect=lambda *_: "c3"),
            patch.object(climate, "MideaFBClimate", side_effect=lambda *_: "fb"),
        ):
            await climate.async_setup_entry(hass, config_entry, add_entities)
        assert add_entities.called

        for dev_type in (
            DeviceType.CC,
            DeviceType.CF,
            DeviceType.C3,
            DeviceType.FB,
        ):
            add_entities.reset_mock()
            hass.data[DOMAIN][DEVICES][123] = DummyDevice(dev_type)
            with (
                patch.object(climate, "MideaACClimate", side_effect=lambda *_: "ac"),
                patch.object(climate, "MideaCCClimate", side_effect=lambda *_: "cc"),
                patch.object(climate, "MideaCFClimate", side_effect=lambda *_: "cf"),
                patch.object(climate, "MideaC3Climate", side_effect=lambda *_: "c3"),
                patch.object(climate, "MideaFBClimate", side_effect=lambda *_: "fb"),
            ):
                await climate.async_setup_entry(hass, config_entry, add_entities)
            assert add_entities.called
