"""Support for KNX button entities."""

from typing import Any, override

from xknx.devices import ExposeSensor as XknxExposeSensor, RawValue as XknxRawValue

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, CONF_PAYLOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PAYLOAD_LENGTH, CONF_VALUE, DOMAIN, KNX_ADDRESS, KNX_MODULE_KEY
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .knx_module import KNXModule
from .storage.const import CONF_DATA, CONF_ENTITY, CONF_GA_SEND
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.BUTTON,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiButton,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.BUTTON):
        entities.extend(
            KnxYamlButton(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.BUTTON):
        entities.extend(
            KnxUiButton(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxButton(ButtonEntity):
    """Representation of a KNX button."""

    _device: XknxRawValue | XknxExposeSensor
    _payload: Any

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._device.set(self._payload)


class KnxYamlButton(_KnxButton, KnxYamlEntity):
    """Representation of a KNX button configured via YAML."""

    _device: XknxRawValue

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX button."""
        # dpt-value to payload conversion is done in schema validation for yaml config
        self._payload = config[CONF_PAYLOAD]
        self._device = XknxRawValue(
            xknx=knx_module.xknx,
            name=config[CONF_NAME],
            payload_length=config[CONF_PAYLOAD_LENGTH],
            group_address=config[KNX_ADDRESS],
        )
        super().__init__(
            knx_module=knx_module,
            unique_id=f"{self._device.remote_value.group_address}_{self._payload}",
            name=config[CONF_NAME],
            entity_category=config.get(CONF_ENTITY_CATEGORY),
        )


class KnxUiButton(_KnxButton, KnxUiEntity):
    """Representation of a KNX button configured via the UI."""

    _device: XknxRawValue | XknxExposeSensor

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize a KNX button."""
        knx_conf = ConfigExtractor(config[DOMAIN])
        button_data = knx_conf.get(CONF_DATA)
        if CONF_PAYLOAD in button_data and CONF_PAYLOAD_LENGTH in button_data:
            self._payload = int(button_data[CONF_PAYLOAD], 16)
            self._device = XknxRawValue(
                xknx=knx_module.xknx,
                name=config[CONF_ENTITY][CONF_NAME],
                payload_length=button_data[CONF_PAYLOAD_LENGTH],
                group_address=knx_conf.get_write(CONF_GA_SEND),
            )
        else:
            dpt_string = knx_conf.get_dpt(CONF_GA_SEND)
            self._payload = button_data[CONF_VALUE]
            self._device = XknxExposeSensor(
                xknx=knx_module.xknx,
                name=config[CONF_ENTITY][CONF_NAME],
                value_type=dpt_string,
                group_address=knx_conf.get_write(CONF_GA_SEND),
                respond_to_read=False,
            )

        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
