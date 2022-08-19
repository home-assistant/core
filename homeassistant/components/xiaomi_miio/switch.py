"""Support for Xiaomi Smart WiFi Socket and Smart Power Strip."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
import logging

from miio import AirConditioningCompanionV3, ChuangmiPlug, DeviceException, PowerStrip
from miio.powerstrip import PowerMode
import voluptuous as vol

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_MODEL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    DOMAIN,
    FEATURE_FLAGS_AIRFRESH,
    FEATURE_FLAGS_AIRFRESH_A1,
    FEATURE_FLAGS_AIRFRESH_T2017,
    FEATURE_FLAGS_AIRFRESH_VA4,
    FEATURE_FLAGS_AIRHUMIDIFIER,
    FEATURE_FLAGS_AIRHUMIDIFIER_CA4,
    FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB,
    FEATURE_FLAGS_AIRHUMIDIFIER_MJSSQ,
    FEATURE_FLAGS_AIRPURIFIER_2S,
    FEATURE_FLAGS_AIRPURIFIER_3C,
    FEATURE_FLAGS_AIRPURIFIER_4,
    FEATURE_FLAGS_AIRPURIFIER_MIIO,
    FEATURE_FLAGS_AIRPURIFIER_MIOT,
    FEATURE_FLAGS_AIRPURIFIER_PRO,
    FEATURE_FLAGS_AIRPURIFIER_PRO_V7,
    FEATURE_FLAGS_AIRPURIFIER_V1,
    FEATURE_FLAGS_AIRPURIFIER_V3,
    FEATURE_FLAGS_FAN,
    FEATURE_FLAGS_FAN_1C,
    FEATURE_FLAGS_FAN_P5,
    FEATURE_FLAGS_FAN_P9,
    FEATURE_FLAGS_FAN_P10_P11,
    FEATURE_FLAGS_FAN_ZA5,
    FEATURE_SET_ANION,
    FEATURE_SET_AUTO_DETECT,
    FEATURE_SET_BUZZER,
    FEATURE_SET_CHILD_LOCK,
    FEATURE_SET_CLEAN,
    FEATURE_SET_DISPLAY,
    FEATURE_SET_DRY,
    FEATURE_SET_IONIZER,
    FEATURE_SET_LEARN_MODE,
    FEATURE_SET_LED,
    FEATURE_SET_PTC,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017,
    MODEL_AIRFRESH_VA2,
    MODEL_AIRFRESH_VA4,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODEL_AIRPURIFIER_2H,
    MODEL_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_3C,
    MODEL_AIRPURIFIER_4,
    MODEL_AIRPURIFIER_4_PRO,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V1,
    MODEL_AIRPURIFIER_V3,
    MODEL_FAN_1C,
    MODEL_FAN_P5,
    MODEL_FAN_P9,
    MODEL_FAN_P10,
    MODEL_FAN_P11,
    MODEL_FAN_ZA1,
    MODEL_FAN_ZA3,
    MODEL_FAN_ZA4,
    MODEL_FAN_ZA5,
    MODELS_FAN,
    MODELS_HUMIDIFIER,
    MODELS_HUMIDIFIER_MJJSQ,
    MODELS_PURIFIER_MIIO,
    MODELS_PURIFIER_MIOT,
    SERVICE_SET_POWER_MODE,
    SERVICE_SET_POWER_PRICE,
    SERVICE_SET_WIFI_LED_OFF,
    SERVICE_SET_WIFI_LED_ON,
    SUCCESS,
)
from .device import XiaomiCoordinatedMiioEntity, XiaomiMiioEntity
from .gateway import XiaomiGatewayDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Switch"
DATA_KEY = "switch.xiaomi_miio"

MODEL_POWER_STRIP_V2 = "zimi.powerstrip.v2"
MODEL_PLUG_V3 = "chuangmi.plug.v3"

KEY_CHANNEL = "channel"
GATEWAY_SWITCH_VARS = {
    "status_ch0": {KEY_CHANNEL: 0},
    "status_ch1": {KEY_CHANNEL: 1},
    "status_ch2": {KEY_CHANNEL: 2},
}


ATTR_AUTO_DETECT = "auto_detect"
ATTR_BUZZER = "buzzer"
ATTR_CHILD_LOCK = "child_lock"
ATTR_CLEAN = "clean_mode"
ATTR_DISPLAY = "display"
ATTR_DRY = "dry"
ATTR_LEARN_MODE = "learn_mode"
ATTR_LED = "led"
ATTR_IONIZER = "ionizer"
ATTR_ANION = "anion"
ATTR_LOAD_POWER = "load_power"
ATTR_MODEL = "model"
ATTR_POWER = "power"
ATTR_POWER_MODE = "power_mode"
ATTR_POWER_PRICE = "power_price"
ATTR_PRICE = "price"
ATTR_PTC = "ptc"
ATTR_WIFI_LED = "wifi_led"

FEATURE_SET_POWER_MODE = 1
FEATURE_SET_WIFI_LED = 2
FEATURE_SET_POWER_PRICE = 4

FEATURE_FLAGS_GENERIC = 0

FEATURE_FLAGS_POWER_STRIP_V1 = (
    FEATURE_SET_POWER_MODE | FEATURE_SET_WIFI_LED | FEATURE_SET_POWER_PRICE
)

FEATURE_FLAGS_POWER_STRIP_V2 = FEATURE_SET_WIFI_LED | FEATURE_SET_POWER_PRICE

FEATURE_FLAGS_PLUG_V3 = FEATURE_SET_WIFI_LED

SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_POWER_MODE = SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_MODE): vol.All(vol.In(["green", "normal"]))}
)

SERVICE_SCHEMA_POWER_PRICE = SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_PRICE): cv.positive_float}
)

SERVICE_TO_METHOD = {
    SERVICE_SET_WIFI_LED_ON: {"method": "async_set_wifi_led_on"},
    SERVICE_SET_WIFI_LED_OFF: {"method": "async_set_wifi_led_off"},
    SERVICE_SET_POWER_MODE: {
        "method": "async_set_power_mode",
        "schema": SERVICE_SCHEMA_POWER_MODE,
    },
    SERVICE_SET_POWER_PRICE: {
        "method": "async_set_power_price",
        "schema": SERVICE_SCHEMA_POWER_PRICE,
    },
}

MODEL_TO_FEATURES_MAP = {
    MODEL_AIRFRESH_A1: FEATURE_FLAGS_AIRFRESH_A1,
    MODEL_AIRFRESH_VA2: FEATURE_FLAGS_AIRFRESH,
    MODEL_AIRFRESH_VA4: FEATURE_FLAGS_AIRFRESH_VA4,
    MODEL_AIRFRESH_T2017: FEATURE_FLAGS_AIRFRESH_T2017,
    MODEL_AIRHUMIDIFIER_CA1: FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB,
    MODEL_AIRHUMIDIFIER_CA4: FEATURE_FLAGS_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1: FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB,
    MODEL_AIRPURIFIER_2H: FEATURE_FLAGS_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_2S: FEATURE_FLAGS_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_3C: FEATURE_FLAGS_AIRPURIFIER_3C,
    MODEL_AIRPURIFIER_PRO: FEATURE_FLAGS_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7: FEATURE_FLAGS_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V1: FEATURE_FLAGS_AIRPURIFIER_V1,
    MODEL_AIRPURIFIER_V3: FEATURE_FLAGS_AIRPURIFIER_V3,
    MODEL_AIRPURIFIER_4: FEATURE_FLAGS_AIRPURIFIER_4,
    MODEL_AIRPURIFIER_4_PRO: FEATURE_FLAGS_AIRPURIFIER_4,
    MODEL_FAN_1C: FEATURE_FLAGS_FAN_1C,
    MODEL_FAN_P10: FEATURE_FLAGS_FAN_P10_P11,
    MODEL_FAN_P11: FEATURE_FLAGS_FAN_P10_P11,
    MODEL_FAN_P5: FEATURE_FLAGS_FAN_P5,
    MODEL_FAN_P9: FEATURE_FLAGS_FAN_P9,
    MODEL_FAN_ZA1: FEATURE_FLAGS_FAN,
    MODEL_FAN_ZA3: FEATURE_FLAGS_FAN,
    MODEL_FAN_ZA4: FEATURE_FLAGS_FAN,
    MODEL_FAN_ZA5: FEATURE_FLAGS_FAN_ZA5,
}


@dataclass
class XiaomiMiioSwitchRequiredKeyMixin:
    """A class that describes switch entities."""

    feature: int
    method_on: str
    method_off: str


@dataclass
class XiaomiMiioSwitchDescription(
    SwitchEntityDescription, XiaomiMiioSwitchRequiredKeyMixin
):
    """A class that describes switch entities."""

    available_with_device_off: bool = True


SWITCH_TYPES = (
    XiaomiMiioSwitchDescription(
        key=ATTR_BUZZER,
        feature=FEATURE_SET_BUZZER,
        name="Buzzer",
        icon="mdi:volume-high",
        method_on="async_set_buzzer_on",
        method_off="async_set_buzzer_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_CHILD_LOCK,
        feature=FEATURE_SET_CHILD_LOCK,
        name="Child lock",
        icon="mdi:lock",
        method_on="async_set_child_lock_on",
        method_off="async_set_child_lock_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_DISPLAY,
        feature=FEATURE_SET_DISPLAY,
        name="Display",
        icon="mdi:led-outline",
        method_on="async_set_display_on",
        method_off="async_set_display_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_DRY,
        feature=FEATURE_SET_DRY,
        name="Dry mode",
        icon="mdi:hair-dryer",
        method_on="async_set_dry_on",
        method_off="async_set_dry_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_CLEAN,
        feature=FEATURE_SET_CLEAN,
        name="Clean mode",
        icon="mdi:shimmer",
        method_on="async_set_clean_on",
        method_off="async_set_clean_off",
        available_with_device_off=False,
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_LED,
        feature=FEATURE_SET_LED,
        name="LED",
        icon="mdi:led-outline",
        method_on="async_set_led_on",
        method_off="async_set_led_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_LEARN_MODE,
        feature=FEATURE_SET_LEARN_MODE,
        name="Learn mode",
        icon="mdi:school-outline",
        method_on="async_set_learn_mode_on",
        method_off="async_set_learn_mode_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_AUTO_DETECT,
        feature=FEATURE_SET_AUTO_DETECT,
        name="Auto detect",
        method_on="async_set_auto_detect_on",
        method_off="async_set_auto_detect_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_IONIZER,
        feature=FEATURE_SET_IONIZER,
        name="Ionizer",
        icon="mdi:shimmer",
        method_on="async_set_ionizer_on",
        method_off="async_set_ionizer_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_ANION,
        feature=FEATURE_SET_ANION,
        name="Ionizer",
        icon="mdi:shimmer",
        method_on="async_set_anion_on",
        method_off="async_set_anion_off",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSwitchDescription(
        key=ATTR_PTC,
        feature=FEATURE_SET_PTC,
        name="Auxiliary heat",
        icon="mdi:radiator",
        method_on="async_set_ptc_on",
        method_off="async_set_ptc_off",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch from a config entry."""
    model = config_entry.data[CONF_MODEL]
    if model in (*MODELS_HUMIDIFIER, *MODELS_FAN):
        await async_setup_coordinated_entry(hass, config_entry, async_add_entities)
    else:
        await async_setup_other_entry(hass, config_entry, async_add_entities)


async def async_setup_coordinated_entry(hass, config_entry, async_add_entities):
    """Set up the coordinated switch from a config entry."""
    entities = []
    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    device_features = 0

    if model in MODEL_TO_FEATURES_MAP:
        device_features = MODEL_TO_FEATURES_MAP[model]
    elif model in MODELS_HUMIDIFIER_MJJSQ:
        device_features = FEATURE_FLAGS_AIRHUMIDIFIER_MJSSQ
    elif model in MODELS_HUMIDIFIER:
        device_features = FEATURE_FLAGS_AIRHUMIDIFIER
    elif model in MODELS_PURIFIER_MIIO:
        device_features = FEATURE_FLAGS_AIRPURIFIER_MIIO
    elif model in MODELS_PURIFIER_MIOT:
        device_features = FEATURE_FLAGS_AIRPURIFIER_MIOT

    for description in SWITCH_TYPES:
        if description.feature & device_features:
            entities.append(
                XiaomiGenericCoordinatedSwitch(
                    device,
                    config_entry,
                    f"{description.key}_{unique_id}",
                    coordinator,
                    description,
                )
            )

    async_add_entities(entities)


async def async_setup_other_entry(hass, config_entry, async_add_entities):
    """Set up the other type switch from a config entry."""
    entities = []
    host = config_entry.data[CONF_HOST]
    token = config_entry.data[CONF_TOKEN]
    name = config_entry.title
    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id
    if config_entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY:
        gateway = hass.data[DOMAIN][config_entry.entry_id][CONF_GATEWAY]
        # Gateway sub devices
        sub_devices = gateway.devices
        for sub_device in sub_devices.values():
            if sub_device.device_type != "Switch":
                continue
            coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR][
                sub_device.sid
            ]
            switch_variables = set(sub_device.status) & set(GATEWAY_SWITCH_VARS)
            if switch_variables:
                entities.extend(
                    [
                        XiaomiGatewaySwitch(
                            coordinator, sub_device, config_entry, variable
                        )
                        for variable in switch_variables
                    ]
                )

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE or (
        config_entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY
        and model == "lumi.acpartner.v3"
    ):
        if DATA_KEY not in hass.data:
            hass.data[DATA_KEY] = {}

        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        if model in ["chuangmi.plug.v1", "chuangmi.plug.v3", "chuangmi.plug.hmi208"]:
            plug = ChuangmiPlug(host, token, model=model)

            # The device has two switchable channels (mains and a USB port).
            # A switch device per channel will be created.
            for channel_usb in (True, False):
                if channel_usb:
                    unique_id_ch = f"{unique_id}-USB"
                else:
                    unique_id_ch = f"{unique_id}-mains"
                device = ChuangMiPlugSwitch(
                    name, plug, config_entry, unique_id_ch, channel_usb
                )
                entities.append(device)
                hass.data[DATA_KEY][host] = device
        elif model in ["qmi.powerstrip.v1", "zimi.powerstrip.v2"]:
            plug = PowerStrip(host, token, model=model)
            device = XiaomiPowerStripSwitch(name, plug, config_entry, unique_id)
            entities.append(device)
            hass.data[DATA_KEY][host] = device
        elif model in [
            "chuangmi.plug.m1",
            "chuangmi.plug.m3",
            "chuangmi.plug.v2",
            "chuangmi.plug.hmi205",
            "chuangmi.plug.hmi206",
        ]:
            plug = ChuangmiPlug(host, token, model=model)
            device = XiaomiPlugGenericSwitch(name, plug, config_entry, unique_id)
            entities.append(device)
            hass.data[DATA_KEY][host] = device
        elif model in ["lumi.acpartner.v3"]:
            plug = AirConditioningCompanionV3(host, token)
            device = XiaomiAirConditioningCompanionSwitch(
                name, plug, config_entry, unique_id
            )
            entities.append(device)
            hass.data[DATA_KEY][host] = device
        else:
            _LOGGER.error(
                "Unsupported device found! Please create an issue at "
                "https://github.com/rytilahti/python-miio/issues "
                "and provide the following data: %s",
                model,
            )

        async def async_service_handler(service: ServiceCall) -> None:
            """Map services to methods on XiaomiPlugGenericSwitch."""
            method = SERVICE_TO_METHOD[service.service]
            params = {
                key: value
                for key, value in service.data.items()
                if key != ATTR_ENTITY_ID
            }
            if entity_ids := service.data.get(ATTR_ENTITY_ID):
                devices = [
                    device
                    for device in hass.data[DATA_KEY].values()
                    if device.entity_id in entity_ids
                ]
            else:
                devices = hass.data[DATA_KEY].values()

            update_tasks = []
            for device in devices:
                if not hasattr(device, method["method"]):
                    continue
                await getattr(device, method["method"])(**params)
                update_tasks.append(device.async_update_ha_state(True))

            if update_tasks:
                await asyncio.wait(update_tasks)

        for plug_service, method in SERVICE_TO_METHOD.items():
            schema = method.get("schema", SERVICE_SCHEMA)
            hass.services.async_register(
                DOMAIN, plug_service, async_service_handler, schema=schema
            )

    async_add_entities(entities)


class XiaomiGenericCoordinatedSwitch(XiaomiCoordinatedMiioEntity, SwitchEntity):
    """Representation of a Xiaomi Plug Generic."""

    entity_description: XiaomiMiioSwitchDescription

    def __init__(self, device, entry, unique_id, coordinator, description):
        """Initialize the plug switch."""
        super().__init__(device, entry, unique_id, coordinator)

        self._attr_is_on = self._extract_value_from_attribute(
            self.coordinator.data, description.key
        )
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        self._attr_is_on = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        self.async_write_ha_state()

    @property
    def available(self):
        """Return true when state is known."""
        if (
            super().available
            and not self.coordinator.data.is_on
            and not self.entity_description.available_with_device_off
        ):
            return False
        return super().available

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on an option of the miio device."""
        method = getattr(self, self.entity_description.method_on)
        if await method():
            # Write state back to avoid switch flips with a slow response
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off an option of the miio device."""
        method = getattr(self, self.entity_description.method_off)
        if await method():
            # Write state back to avoid switch flips with a slow response
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_set_buzzer_on(self) -> bool:
        """Turn the buzzer on."""
        return await self._try_command(
            "Turning the buzzer of the miio device on failed.",
            self._device.set_buzzer,
            True,
        )

    async def async_set_buzzer_off(self) -> bool:
        """Turn the buzzer off."""
        return await self._try_command(
            "Turning the buzzer of the miio device off failed.",
            self._device.set_buzzer,
            False,
        )

    async def async_set_child_lock_on(self) -> bool:
        """Turn the child lock on."""
        return await self._try_command(
            "Turning the child lock of the miio device on failed.",
            self._device.set_child_lock,
            True,
        )

    async def async_set_child_lock_off(self) -> bool:
        """Turn the child lock off."""
        return await self._try_command(
            "Turning the child lock of the miio device off failed.",
            self._device.set_child_lock,
            False,
        )

    async def async_set_display_on(self) -> bool:
        """Turn the display on."""
        return await self._try_command(
            "Turning the display of the miio device on failed.",
            self._device.set_display,
            True,
        )

    async def async_set_display_off(self) -> bool:
        """Turn the display off."""
        return await self._try_command(
            "Turning the display of the miio device off failed.",
            self._device.set_display,
            False,
        )

    async def async_set_dry_on(self) -> bool:
        """Turn the dry mode on."""
        return await self._try_command(
            "Turning the dry mode of the miio device on failed.",
            self._device.set_dry,
            True,
        )

    async def async_set_dry_off(self) -> bool:
        """Turn the dry mode off."""
        return await self._try_command(
            "Turning the dry mode of the miio device off failed.",
            self._device.set_dry,
            False,
        )

    async def async_set_clean_on(self) -> bool:
        """Turn the dry mode on."""
        return await self._try_command(
            "Turning the clean mode of the miio device on failed.",
            self._device.set_clean_mode,
            True,
        )

    async def async_set_clean_off(self) -> bool:
        """Turn the dry mode off."""
        return await self._try_command(
            "Turning the clean mode of the miio device off failed.",
            self._device.set_clean_mode,
            False,
        )

    async def async_set_led_on(self) -> bool:
        """Turn the led on."""
        return await self._try_command(
            "Turning the led of the miio device on failed.",
            self._device.set_led,
            True,
        )

    async def async_set_led_off(self) -> bool:
        """Turn the led off."""
        return await self._try_command(
            "Turning the led of the miio device off failed.",
            self._device.set_led,
            False,
        )

    async def async_set_learn_mode_on(self) -> bool:
        """Turn the learn mode on."""
        return await self._try_command(
            "Turning the learn mode of the miio device on failed.",
            self._device.set_learn_mode,
            True,
        )

    async def async_set_learn_mode_off(self) -> bool:
        """Turn the learn mode off."""
        return await self._try_command(
            "Turning the learn mode of the miio device off failed.",
            self._device.set_learn_mode,
            False,
        )

    async def async_set_auto_detect_on(self) -> bool:
        """Turn auto detect on."""
        return await self._try_command(
            "Turning auto detect of the miio device on failed.",
            self._device.set_auto_detect,
            True,
        )

    async def async_set_auto_detect_off(self) -> bool:
        """Turn auto detect off."""
        return await self._try_command(
            "Turning auto detect of the miio device off failed.",
            self._device.set_auto_detect,
            False,
        )

    async def async_set_ionizer_on(self) -> bool:
        """Turn ionizer on."""
        return await self._try_command(
            "Turning ionizer of the miio device on failed.",
            self._device.set_ionizer,
            True,
        )

    async def async_set_ionizer_off(self) -> bool:
        """Turn ionizer off."""
        return await self._try_command(
            "Turning ionizer of the miio device off failed.",
            self._device.set_ionizer,
            False,
        )

    async def async_set_anion_on(self) -> bool:
        """Turn ionizer on."""
        return await self._try_command(
            "Turning ionizer of the miio device on failed.",
            self._device.set_anion,
            True,
        )

    async def async_set_anion_off(self) -> bool:
        """Turn ionizer off."""
        return await self._try_command(
            "Turning ionizer of the miio device off failed.",
            self._device.set_anion,
            False,
        )

    async def async_set_ptc_on(self) -> bool:
        """Turn ionizer on."""
        return await self._try_command(
            "Turning ionizer of the miio device on failed.",
            self._device.set_ptc,
            True,
        )

    async def async_set_ptc_off(self) -> bool:
        """Turn ionizer off."""
        return await self._try_command(
            "Turning ionizer of the miio device off failed.",
            self._device.set_ptc,
            False,
        )


class XiaomiGatewaySwitch(XiaomiGatewayDevice, SwitchEntity):
    """Representation of a XiaomiGatewaySwitch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator, sub_device, entry, variable):
        """Initialize the XiaomiSensor."""
        super().__init__(coordinator, sub_device, entry)
        self._channel = GATEWAY_SWITCH_VARS[variable][KEY_CHANNEL]
        self._data_key = f"status_ch{self._channel}"
        self._unique_id = f"{sub_device.sid}-ch{self._channel}"
        self._name = f"{sub_device.name} ch{self._channel} ({sub_device.sid})"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._sub_device.status[self._data_key] == "on"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.hass.async_add_executor_job(self._sub_device.on, self._channel)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self._sub_device.off, self._channel)

    async def async_toggle(self, **kwargs):
        """Toggle the switch."""
        await self.hass.async_add_executor_job(self._sub_device.toggle, self._channel)


class XiaomiPlugGenericSwitch(XiaomiMiioEntity, SwitchEntity):
    """Representation of a Xiaomi Plug Generic."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id)

        self._icon = "mdi:power-socket"
        self._available = False
        self._state = None
        self._state_attrs = {ATTR_TEMPERATURE: None, ATTR_MODEL: self._model}
        self._device_features = FEATURE_FLAGS_GENERIC
        self._skip_update = False

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a plug command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from plug: %s", result)

            # The Chuangmi Plug V3 returns 0 on success on usb_on/usb_off.
            if func in ["usb_on", "usb_off"] and result == 0:
                return True

            return result == SUCCESS
        except DeviceException as exc:
            if self._available:
                _LOGGER.error(mask_error, exc)
                self._available = False

            return False

    async def async_turn_on(self, **kwargs):
        """Turn the plug on."""
        result = await self._try_command("Turning the plug on failed", self._device.on)

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn the plug off."""
        result = await self._try_command(
            "Turning the plug off failed", self._device.off
        )

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs[ATTR_TEMPERATURE] = state.temperature

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def async_set_wifi_led_on(self):
        """Turn the wifi led on."""
        if self._device_features & FEATURE_SET_WIFI_LED == 0:
            return

        await self._try_command(
            "Turning the wifi led on failed", self._device.set_wifi_led, True
        )

    async def async_set_wifi_led_off(self):
        """Turn the wifi led on."""
        if self._device_features & FEATURE_SET_WIFI_LED == 0:
            return

        await self._try_command(
            "Turning the wifi led off failed", self._device.set_wifi_led, False
        )

    async def async_set_power_price(self, price: int):
        """Set the power price."""
        if self._device_features & FEATURE_SET_POWER_PRICE == 0:
            return

        await self._try_command(
            "Setting the power price of the power strip failed",
            self._device.set_power_price,
            price,
        )


class XiaomiPowerStripSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Xiaomi Power Strip."""

    def __init__(self, name, plug, model, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, plug, model, unique_id)

        if self._model == MODEL_POWER_STRIP_V2:
            self._device_features = FEATURE_FLAGS_POWER_STRIP_V2
        else:
            self._device_features = FEATURE_FLAGS_POWER_STRIP_V1

        self._state_attrs[ATTR_LOAD_POWER] = None

        if self._device_features & FEATURE_SET_POWER_MODE == 1:
            self._state_attrs[ATTR_POWER_MODE] = None

        if self._device_features & FEATURE_SET_WIFI_LED == 1:
            self._state_attrs[ATTR_WIFI_LED] = None

        if self._device_features & FEATURE_SET_POWER_PRICE == 1:
            self._state_attrs[ATTR_POWER_PRICE] = None

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs.update(
                {ATTR_TEMPERATURE: state.temperature, ATTR_LOAD_POWER: state.load_power}
            )

            if self._device_features & FEATURE_SET_POWER_MODE == 1 and state.mode:
                self._state_attrs[ATTR_POWER_MODE] = state.mode.value

            if self._device_features & FEATURE_SET_WIFI_LED == 1 and state.wifi_led:
                self._state_attrs[ATTR_WIFI_LED] = state.wifi_led

            if (
                self._device_features & FEATURE_SET_POWER_PRICE == 1
                and state.power_price
            ):
                self._state_attrs[ATTR_POWER_PRICE] = state.power_price

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

    async def async_set_power_mode(self, mode: str):
        """Set the power mode."""
        if self._device_features & FEATURE_SET_POWER_MODE == 0:
            return

        await self._try_command(
            "Setting the power mode of the power strip failed",
            self._device.set_power_mode,
            PowerMode(mode),
        )


class ChuangMiPlugSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Chuang Mi Plug V1 and V3."""

    def __init__(self, name, plug, entry, unique_id, channel_usb):
        """Initialize the plug switch."""
        name = f"{name} USB" if channel_usb else name

        if unique_id is not None and channel_usb:
            unique_id = f"{unique_id}-usb"

        super().__init__(name, plug, entry, unique_id)
        self._channel_usb = channel_usb

        if self._model == MODEL_PLUG_V3:
            self._device_features = FEATURE_FLAGS_PLUG_V3
            self._state_attrs[ATTR_WIFI_LED] = None
            if self._channel_usb is False:
                self._state_attrs[ATTR_LOAD_POWER] = None

    async def async_turn_on(self, **kwargs):
        """Turn a channel on."""
        if self._channel_usb:
            result = await self._try_command(
                "Turning the plug on failed", self._device.usb_on
            )
        else:
            result = await self._try_command(
                "Turning the plug on failed", self._device.on
            )

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn a channel off."""
        if self._channel_usb:
            result = await self._try_command(
                "Turning the plug off failed", self._device.usb_off
            )
        else:
            result = await self._try_command(
                "Turning the plug off failed", self._device.off
            )

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            if self._channel_usb:
                self._state = state.usb_power
            else:
                self._state = state.is_on

            self._state_attrs[ATTR_TEMPERATURE] = state.temperature

            if state.wifi_led:
                self._state_attrs[ATTR_WIFI_LED] = state.wifi_led

            if self._channel_usb is False and state.load_power:
                self._state_attrs[ATTR_LOAD_POWER] = state.load_power

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)


class XiaomiAirConditioningCompanionSwitch(XiaomiPlugGenericSwitch):
    """Representation of a Xiaomi AirConditioning Companion."""

    def __init__(self, name, plug, model, unique_id):
        """Initialize the acpartner switch."""
        super().__init__(name, plug, model, unique_id)

        self._state_attrs.update({ATTR_TEMPERATURE: None, ATTR_LOAD_POWER: None})

    async def async_turn_on(self, **kwargs):
        """Turn the socket on."""
        result = await self._try_command(
            "Turning the socket on failed", self._device.socket_on
        )

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs):
        """Turn the socket off."""
        result = await self._try_command(
            "Turning the socket off failed", self._device.socket_off
        )

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.power_socket == "on"
            self._state_attrs[ATTR_LOAD_POWER] = state.load_power

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)
