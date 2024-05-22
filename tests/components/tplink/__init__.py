"""Tests for the TP-Link component."""

from collections import namedtuple
from typing import Any, TypedDict
from unittest.mock import AsyncMock, MagicMock, patch

from kasa import (
    ConnectionType,
    Device,
    DeviceConfig,
    DeviceFamilyType,
    DeviceType,
    EncryptType,
    Feature,
    KasaException,
    Module,
)
from kasa.interfaces import Led, Light, LightEffect
from kasa.protocol import BaseProtocol

from homeassistant.components.tplink import (
    CONF_ALIAS,
    CONF_DEVICE_CONFIG,
    CONF_HOST,
    CONF_MODEL,
    Credentials,
)
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ColorTempRange = namedtuple("ColorTempRange", ["min", "max"])

MODULE = "homeassistant.components.tplink"
MODULE_CONFIG_FLOW = "homeassistant.components.tplink.config_flow"
IP_ADDRESS = "127.0.0.1"
IP_ADDRESS2 = "127.0.0.2"
ALIAS = "My Bulb"
MODEL = "HS100"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
DHCP_FORMATTED_MAC_ADDRESS = MAC_ADDRESS.replace(":", "")
MAC_ADDRESS2 = "11:22:33:44:55:66"
DEFAULT_ENTRY_TITLE = f"{ALIAS} {MODEL}"
CREDENTIALS_HASH_LEGACY = ""
DEVICE_CONFIG_LEGACY = DeviceConfig(IP_ADDRESS)
DEVICE_CONFIG_DICT_LEGACY = DEVICE_CONFIG_LEGACY.to_dict(
    credentials_hash=CREDENTIALS_HASH_LEGACY, exclude_credentials=True
)
CREDENTIALS = Credentials("foo", "bar")
CREDENTIALS_HASH_AUTH = "abcdefghijklmnopqrstuv=="
DEVICE_CONFIG_AUTH = DeviceConfig(
    IP_ADDRESS,
    credentials=CREDENTIALS,
    connection_type=ConnectionType(
        DeviceFamilyType.IotSmartPlugSwitch, EncryptType.Klap
    ),
    uses_http=True,
)
DEVICE_CONFIG_AUTH2 = DeviceConfig(
    IP_ADDRESS2,
    credentials=CREDENTIALS,
    connection_type=ConnectionType(
        DeviceFamilyType.IotSmartPlugSwitch, EncryptType.Klap
    ),
    uses_http=True,
)
DEVICE_CONFIG_DICT_AUTH = DEVICE_CONFIG_AUTH.to_dict(
    credentials_hash=CREDENTIALS_HASH_AUTH, exclude_credentials=True
)
DEVICE_CONFIG_DICT_AUTH2 = DEVICE_CONFIG_AUTH2.to_dict(
    credentials_hash=CREDENTIALS_HASH_AUTH, exclude_credentials=True
)

CREATE_ENTRY_DATA_LEGACY = {
    CONF_HOST: IP_ADDRESS,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_LEGACY,
}

CREATE_ENTRY_DATA_AUTH = {
    CONF_HOST: IP_ADDRESS,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH,
}
CREATE_ENTRY_DATA_AUTH2 = {
    CONF_HOST: IP_ADDRESS2,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_DEVICE_CONFIG: DEVICE_CONFIG_DICT_AUTH2,
}


def _mock_protocol() -> BaseProtocol:
    protocol = MagicMock(auto_spec=BaseProtocol)
    protocol.close = AsyncMock()
    return protocol


def _mocked_device(
    device_config=DEVICE_CONFIG_LEGACY,
    credentials_hash=CREDENTIALS_HASH_LEGACY,
    mac=MAC_ADDRESS,
    device_id=MAC_ADDRESS,
    alias=ALIAS,
    modules: list[str] | None = None,
    children: list[Device] | None = None,
    features: list[str] | None = None,
    device_type=DeviceType.Unknown,
) -> Device:
    device = MagicMock(auto_spec=Device, name="Mocked device")
    device.update = AsyncMock()
    device.mac = mac
    device.alias = alias
    device.model = MODEL
    device.host = IP_ADDRESS
    device.device_id = device_id
    device.hw_info = {"sw_ver": "1.0.0", "hw_ver": "1.0.0"}
    device.turn_off = AsyncMock()
    device.turn_on = AsyncMock()

    device.modules = (
        {module_name: MODULE_TO_MOCK_GEN[module_name]() for module_name in modules}
        if modules
        else {}
    )

    device.features = (
        {feature_id: FEATURE_TO_MOCK_GEN[feature_id]() for feature_id in features}
        if features
        else {}
    )

    device.children = children if children else []
    device.device_type = device_type
    if device.children and all(
        child.device_type == DeviceType.StripSocket for child in device.children
    ):
        device.device_type = DeviceType.Strip

    device.protocol = _mock_protocol()
    device.config = device_config
    device.credentials_hash = credentials_hash
    return device


def _mocked_feature(
    value: Any, id: str, type_=Feature.Type.Sensor, category=Feature.Category.Debug
) -> Feature:
    feature = MagicMock(auto_spec=Feature, name="Mocked feature")
    feature.id = id
    feature.name = id
    feature.value = value
    feature.type = type_
    feature.category = category
    feature.set_value = AsyncMock()
    return feature


def _mocked_light_module() -> Light:
    light = MagicMock(auto_spec=Light, name="Mocked light module")
    light.update = AsyncMock()
    light.brightness = 50
    light.color_temp = 4000
    light.is_color = True
    light.is_variable_color_temp = True
    light.is_dimmable = True
    light.is_brightness = True
    light.has_effects = False
    light.hsv = (10, 30, 5)
    light.valid_temperature_range = ColorTempRange(min=4000, max=9000)
    light.hw_info = {"sw_ver": "1.0.0", "hw_ver": "1.0.0"}
    light.set_state = AsyncMock()
    light.set_brightness = AsyncMock()
    light.set_hsv = AsyncMock()
    light.set_color_temp = AsyncMock()
    light.protocol = _mock_protocol()
    return light


def _mocked_light_effect_module() -> LightEffect:
    effect = MagicMock(auto_spec=LightEffect, name="Mocked light effect")
    effect.has_effects = True
    effect.has_custom_effects = True
    effect.effect = "Effect1"
    effect.effect_list = ["Off", "Effect1", "Effect2"]
    effect.set_effect = AsyncMock()
    effect.set_custom_effect = AsyncMock()
    return effect


def _mocked_led_module() -> Led:
    led_module = MagicMock(auto_spec=Led, name="Mocked led")
    led_module.led = True
    led_module.set_led = AsyncMock()
    return led_module


def _mocked_strip_children(features=None) -> list[Device]:
    plug0 = _mocked_device(
        alias="Plug0",
        device_id="bb:bb:cc:dd:ee:ff_PLUG0DEVICEID",
        mac="bb:bb:cc:dd:ee:ff",
        device_type=DeviceType.StripSocket,
        features=features,
    )
    plug1 = _mocked_device(
        alias="Plug1",
        device_id="cc:bb:cc:dd:ee:ff_PLUG1DEVICEID",
        mac="cc:bb:cc:dd:ee:ff",
        device_type=DeviceType.StripSocket,
        features=features,
    )
    plug0.is_on = True
    plug1.is_on = False
    return [plug0, plug1]


MODULE_TO_MOCK_GEN = {
    Module.Light: _mocked_light_module,
    Module.LightEffect: _mocked_light_effect_module,
    Module.Led: _mocked_led_module,
}

FEATURE_TO_MOCK_GEN = {
    "state": lambda: _mocked_feature(
        True, "state", Feature.Type.Switch, Feature.Category.Primary
    ),
    "led": lambda: _mocked_feature(
        True, "led", Feature.Type.Switch, Feature.Category.Config
    ),
}


def _patch_discovery(device=None, no_device=False):
    async def _discovery(*args, **kwargs):
        if no_device:
            return {}
        return {IP_ADDRESS: _mocked_device()}

    return patch("homeassistant.components.tplink.Discover.discover", new=_discovery)


def _patch_single_discovery(device=None, no_device=False):
    async def _discover_single(*args, **kwargs):
        if no_device:
            raise KasaException
        return device if device else _mocked_device()

    return patch(
        "homeassistant.components.tplink.Discover.discover_single", new=_discover_single
    )


def _patch_connect(device=None, no_device=False):
    async def _connect(*args, **kwargs):
        if no_device:
            raise KasaException
        return device if device else _mocked_device()

    return patch("homeassistant.components.tplink.Device.connect", new=_connect)


async def initialize_config_entry_for_device(
    hass: HomeAssistant, dev: Device
) -> MockConfigEntry:
    """Create a mocked configuration entry for the given device.

    Note, the rest of the tests should probably be converted over to use this
    instead of repeating the initialization routine for each test separately
    """
    config_entry = MockConfigEntry(
        title="TP-Link", domain=DOMAIN, unique_id=dev.mac, data={CONF_HOST: dev.host}
    )
    config_entry.add_to_hass(hass)

    with (
        _patch_discovery(device=dev),
        _patch_single_discovery(device=dev),
        _patch_connect(device=dev),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
