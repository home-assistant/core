"""Tests for the TP-Link component."""

from collections import namedtuple
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from kasa import (
    Device,
    DeviceConfig,
    DeviceConnectionParameters,
    DeviceEncryptionType,
    DeviceFamily,
    DeviceType,
    Feature,
    KasaException,
    Module,
)
from kasa.interfaces import Fan, Light, LightEffect, LightState
from kasa.protocol import BaseProtocol
from kasa.smart.modules.alarm import Alarm
from syrupy import SnapshotAssertion

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.tplink import (
    CONF_AES_KEYS,
    CONF_ALIAS,
    CONF_CONNECTION_PARAMETERS,
    CONF_CREDENTIALS_HASH,
    CONF_HOST,
    CONF_MODEL,
    CONF_USES_HTTP,
    Credentials,
)
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_value_fixture

ColorTempRange = namedtuple("ColorTempRange", ["min", "max"])  # noqa: PYI024

MODULE = "homeassistant.components.tplink"
MODULE_CONFIG_FLOW = "homeassistant.components.tplink.config_flow"
IP_ADDRESS = "127.0.0.1"
IP_ADDRESS2 = "127.0.0.2"
ALIAS = "My Bulb"
MODEL = "HS100"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
DEVICE_ID = "123456789ABCDEFGH"
DEVICE_ID_MAC = "AA:BB:CC:DD:EE:FF"
DHCP_FORMATTED_MAC_ADDRESS = MAC_ADDRESS.replace(":", "")
MAC_ADDRESS2 = "11:22:33:44:55:66"
DEFAULT_ENTRY_TITLE = f"{ALIAS} {MODEL}"
CREDENTIALS_HASH_LEGACY = ""
CONN_PARAMS_LEGACY = DeviceConnectionParameters(
    DeviceFamily.IotSmartPlugSwitch, DeviceEncryptionType.Xor
)
DEVICE_CONFIG_LEGACY = DeviceConfig(IP_ADDRESS)
DEVICE_CONFIG_DICT_LEGACY = DEVICE_CONFIG_LEGACY.to_dict(exclude_credentials=True)
CREDENTIALS = Credentials("foo", "bar")
CREDENTIALS_HASH_AES = "AES/abcdefghijklmnopqrstuvabcdefghijklmnopqrstuv=="
CREDENTIALS_HASH_KLAP = "KLAP/abcdefghijklmnopqrstuv=="
CONN_PARAMS_KLAP = DeviceConnectionParameters(
    DeviceFamily.SmartTapoPlug, DeviceEncryptionType.Klap
)
DEVICE_CONFIG_KLAP = DeviceConfig(
    IP_ADDRESS,
    credentials=CREDENTIALS,
    connection_type=CONN_PARAMS_KLAP,
    uses_http=True,
)
CONN_PARAMS_AES = DeviceConnectionParameters(
    DeviceFamily.SmartTapoPlug, DeviceEncryptionType.Aes
)
AES_KEYS = {"private": "foo", "public": "bar"}
DEVICE_CONFIG_AES = DeviceConfig(
    IP_ADDRESS2,
    credentials=CREDENTIALS,
    connection_type=CONN_PARAMS_AES,
    uses_http=True,
    aes_keys=AES_KEYS,
)
DEVICE_CONFIG_DICT_KLAP = DEVICE_CONFIG_KLAP.to_dict(exclude_credentials=True)
DEVICE_CONFIG_DICT_AES = DEVICE_CONFIG_AES.to_dict(exclude_credentials=True)
CREATE_ENTRY_DATA_LEGACY = {
    CONF_HOST: IP_ADDRESS,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_CONNECTION_PARAMETERS: CONN_PARAMS_LEGACY.to_dict(),
    CONF_USES_HTTP: False,
}

CREATE_ENTRY_DATA_KLAP = {
    CONF_HOST: IP_ADDRESS,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_CREDENTIALS_HASH: CREDENTIALS_HASH_KLAP,
    CONF_CONNECTION_PARAMETERS: CONN_PARAMS_KLAP.to_dict(),
    CONF_USES_HTTP: True,
}
CREATE_ENTRY_DATA_AES = {
    CONF_HOST: IP_ADDRESS2,
    CONF_ALIAS: ALIAS,
    CONF_MODEL: MODEL,
    CONF_CREDENTIALS_HASH: CREDENTIALS_HASH_AES,
    CONF_CONNECTION_PARAMETERS: CONN_PARAMS_AES.to_dict(),
    CONF_USES_HTTP: True,
    CONF_AES_KEYS: AES_KEYS,
}


def _load_feature_fixtures():
    fixtures = load_json_value_fixture("features.json", DOMAIN)
    for fixture in fixtures.values():
        if isinstance(fixture["value"], str):
            try:
                time = datetime.strptime(fixture["value"], "%Y-%m-%d %H:%M:%S.%f%z")
                fixture["value"] = time
            except ValueError:
                pass
    return fixtures


FEATURES_FIXTURE = _load_feature_fixtures()


async def setup_platform_for_device(
    hass: HomeAssistant, config_entry: ConfigEntry, platform: Platform, device: Device
):
    """Set up a single tplink platform with a device."""
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.tplink.PLATFORMS", [platform]),
        _patch_discovery(device=device),
        _patch_connect(device=device),
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        # Good practice to wait background tasks in tests see PR #112726
        await hass.async_block_till_done(wait_background_tasks=True)


async def snapshot_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    config_entry_id: str,
) -> None:
    """Snapshot a platform."""
    device_entries = dr.async_entries_for_config_entry(device_registry, config_entry_id)
    assert device_entries
    for device_entry in device_entries:
        assert device_entry == snapshot(
            name=f"{device_entry.name}-entry"
        ), f"device entry snapshot failed for {device_entry.name}"

    entity_entries = er.async_entries_for_config_entry(entity_registry, config_entry_id)
    assert entity_entries
    assert (
        len({entity_entry.domain for entity_entry in entity_entries}) == 1
    ), "Please limit the loaded platforms to 1 platform."

    translations = await async_get_translations(hass, "en", "entity", [DOMAIN])
    unique_device_classes = []
    for entity_entry in entity_entries:
        if entity_entry.translation_key:
            key = f"component.{DOMAIN}.entity.{entity_entry.domain}.{entity_entry.translation_key}.name"
            single_device_class_translation = False
            if key not in translations and entity_entry.original_device_class:
                if entity_entry.original_device_class not in unique_device_classes:
                    single_device_class_translation = True
                    unique_device_classes.append(entity_entry.original_device_class)
            assert (
                (key in translations) or single_device_class_translation
            ), f"No translation or non unique device_class for entity {entity_entry.unique_id}, expected {key}"
        assert entity_entry == snapshot(
            name=f"{entity_entry.entity_id}-entry"
        ), f"entity entry snapshot failed for {entity_entry.entity_id}"
        if entity_entry.disabled_by is None:
            state = hass.states.get(entity_entry.entity_id)
            assert state, f"State not found for {entity_entry.entity_id}"
            assert state == snapshot(
                name=f"{entity_entry.entity_id}-state"
            ), f"state snapshot failed for {entity_entry.entity_id}"


async def setup_automation(hass: HomeAssistant, alias: str, entity_id: str) -> None:
    """Set up an automation for tests."""
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
                "alias": alias,
                "trigger": {"platform": "state", "entity_id": entity_id, "to": "on"},
                "action": {"action": "notify.notify", "metadata": {}, "data": {}},
            }
        },
    )


def _mock_protocol() -> BaseProtocol:
    protocol = MagicMock(spec=BaseProtocol)
    protocol.close = AsyncMock()
    return protocol


def _mocked_device(
    device_config=DEVICE_CONFIG_LEGACY,
    credentials_hash=CREDENTIALS_HASH_LEGACY,
    mac=MAC_ADDRESS,
    device_id=DEVICE_ID,
    alias=ALIAS,
    model=MODEL,
    ip_address: str | None = None,
    modules: list[str] | None = None,
    children: list[Device] | None = None,
    features: list[str | Feature] | None = None,
    device_type=None,
    spec: type = Device,
) -> Device:
    device = MagicMock(spec=spec, name="Mocked device")
    device.update = AsyncMock()
    device.turn_off = AsyncMock()
    device.turn_on = AsyncMock()

    device.mac = mac
    device.alias = alias
    device.model = model
    device.device_id = device_id
    device.hw_info = {"sw_ver": "1.0.0", "hw_ver": "1.0.0"}
    device.modules = {}
    device.features = {}

    if not ip_address:
        ip_address = IP_ADDRESS
    else:
        device_config.host = ip_address
    device.host = ip_address

    if modules:
        device.modules = {
            module_name: MODULE_TO_MOCK_GEN[module_name](device)
            for module_name in modules
        }

    if features:
        device.features = {
            feature_id: _mocked_feature(feature_id, require_fixture=True)
            for feature_id in features
            if isinstance(feature_id, str)
        }

        device.features.update(
            {
                feature.id: feature
                for feature in features
                if isinstance(feature, Feature)
            }
        )
    device.children = []
    if children:
        for child in children:
            child.mac = mac
        device.children = children
    device.device_type = device_type if device_type else DeviceType.Unknown
    if (
        not device_type
        and device.children
        and all(
            child.device_type is DeviceType.StripSocket for child in device.children
        )
    ):
        device.device_type = DeviceType.Strip

    device.protocol = _mock_protocol()
    device.config = device_config
    device.credentials_hash = credentials_hash
    return device


def _mocked_feature(
    id: str,
    *,
    require_fixture=False,
    value: Any = UNDEFINED,
    name=None,
    type_=None,
    category=None,
    precision_hint=None,
    choices=None,
    unit=None,
    minimum_value=0,
    maximum_value=2**16,  # Arbitrary max
) -> Feature:
    """Get a mocked feature.

    If kwargs are provided they will override the attributes for any features defined in fixtures.json
    """
    feature = MagicMock(spec=Feature, name=f"Mocked {id} feature")
    feature.id = id
    feature.name = name or id.upper()
    feature.set_value = AsyncMock()
    if not (fixture := FEATURES_FIXTURE.get(id)):
        assert (
            require_fixture is False
        ), f"No fixture defined for feature {id} and require_fixture is True"
        assert (
            value is not UNDEFINED
        ), f"Value must be provided if feature {id} not defined in features.json"
        fixture = {"value": value, "category": "Primary", "type": "Sensor"}
    elif value is not UNDEFINED:
        fixture["value"] = value
    feature.value = fixture["value"]

    feature.type = type_ or Feature.Type[fixture["type"]]
    feature.category = category or Feature.Category[fixture["category"]]

    # sensor
    feature.precision_hint = precision_hint or fixture.get("precision_hint")
    feature.unit = unit or fixture.get("unit")

    # number
    feature.minimum_value = minimum_value or fixture.get("minimum_value")
    feature.maximum_value = maximum_value or fixture.get("maximum_value")

    # select
    feature.choices = choices or fixture.get("choices")
    return feature


def _mocked_light_module(device) -> Light:
    light = MagicMock(spec=Light, name="Mocked light module")
    light.update = AsyncMock()
    light.brightness = 50
    light.color_temp = 4000
    light.state = LightState(
        light_on=True, brightness=light.brightness, color_temp=light.color_temp
    )
    light.is_color = True
    light.is_variable_color_temp = True
    light.is_dimmable = True
    light.is_brightness = True
    light.has_effects = False
    light.hsv = (10, 30, 5)
    light.valid_temperature_range = ColorTempRange(min=4000, max=9000)
    light.hw_info = {"sw_ver": "1.0.0", "hw_ver": "1.0.0"}

    async def _set_state(state, *_, **__):
        light.state = state

    light.set_state = AsyncMock(wraps=_set_state)

    async def _set_brightness(brightness, *_, **__):
        light.state.brightness = brightness
        light.state.light_on = brightness > 0

    light.set_brightness = AsyncMock(wraps=_set_brightness)

    async def _set_hsv(h, s, v, *_, **__):
        light.state.hue = h
        light.state.saturation = s
        light.state.brightness = v
        light.state.light_on = True

    light.set_hsv = AsyncMock(wraps=_set_hsv)

    async def _set_color_temp(temp, *_, **__):
        light.state.color_temp = temp
        light.state.light_on = True

    light.set_color_temp = AsyncMock(wraps=_set_color_temp)
    light.protocol = _mock_protocol()
    return light


def _mocked_light_effect_module(device) -> LightEffect:
    effect = MagicMock(spec=LightEffect, name="Mocked light effect")
    effect.has_effects = True
    effect.has_custom_effects = True
    effect.effect = "Effect1"
    effect.effect_list = ["Off", "Effect1", "Effect2"]

    async def _set_effect(effect_name, *_, **__):
        assert (
            effect_name in effect.effect_list
        ), f"set_effect '{effect_name}' not in {effect.effect_list}"
        assert device.modules[
            Module.Light
        ], "Need a light module to test set_effect method"
        device.modules[Module.Light].state.light_on = True
        effect.effect = effect_name

    effect.set_effect = AsyncMock(wraps=_set_effect)
    effect.set_custom_effect = AsyncMock()
    return effect


def _mocked_fan_module(effect) -> Fan:
    fan = MagicMock(auto_spec=Fan, name="Mocked fan")
    fan.fan_speed_level = 0
    fan.set_fan_speed_level = AsyncMock()
    return fan


def _mocked_alarm_module(device):
    alarm = MagicMock(auto_spec=Alarm, name="Mocked alarm")
    alarm.active = False
    alarm.play = AsyncMock()
    alarm.stop = AsyncMock()

    return alarm


def _mocked_strip_children(features=None, alias=None) -> list[Device]:
    plug0 = _mocked_device(
        alias="Plug0" if alias is None else alias,
        device_id="bb:bb:cc:dd:ee:ff_PLUG0DEVICEID",
        mac="bb:bb:cc:dd:ee:ff",
        device_type=DeviceType.StripSocket,
        features=features,
    )
    plug1 = _mocked_device(
        alias="Plug1" if alias is None else alias,
        device_id="cc:bb:cc:dd:ee:ff_PLUG1DEVICEID",
        mac="cc:bb:cc:dd:ee:ff",
        device_type=DeviceType.StripSocket,
        features=features,
    )
    plug0.is_on = True
    plug1.is_on = False
    return [plug0, plug1]


def _mocked_energy_features(
    power=None, total=None, voltage=None, current=None, today=None
) -> list[Feature]:
    feats = []
    if power is not None:
        feats.append(
            _mocked_feature(
                "current_consumption",
                value=power,
            )
        )
    if total is not None:
        feats.append(
            _mocked_feature(
                "consumption_total",
                value=total,
            )
        )
    if voltage is not None:
        feats.append(
            _mocked_feature(
                "voltage",
                value=voltage,
            )
        )
    if current is not None:
        feats.append(
            _mocked_feature(
                "current",
                value=current,
            )
        )
    # Today is always reported as 0 by the library rather than none
    feats.append(
        _mocked_feature(
            "consumption_today",
            value=today if today is not None else 0.0,
        )
    )
    return feats


MODULE_TO_MOCK_GEN = {
    Module.Light: _mocked_light_module,
    Module.LightEffect: _mocked_light_effect_module,
    Module.Fan: _mocked_fan_module,
    Module.Alarm: _mocked_alarm_module,
}


def _patch_discovery(device=None, no_device=False, ip_address=IP_ADDRESS):
    async def _discovery(*args, **kwargs):
        if no_device:
            return {}
        return {ip_address: device if device else _mocked_device()}

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
