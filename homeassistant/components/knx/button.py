"""Support for KNX button entities."""

import asyncio
from asyncio import sleep
from typing import Any, override

from xknx.devices import ExposeSensor as XknxExposeSensor, RawValue as XknxRawValue

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_NAME, CONF_PAYLOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_PAYLOAD_LENGTH,
    CONF_RESET_AFTER,
    CONF_VALUE,
    DOMAIN,
    KNX_ADDRESS,
    KNX_MODULE_KEY,
)
from .entity import (
    KnxUiEntity,
    KnxUiEntityPlatformController,
    KnxYamlEntity,
    build_yaml_unique_id,
)
from .knx_module import KNXModule
from .storage.const import CONF_DATA, CONF_ENTITY, CONF_GA_SEND, CONF_RESET_DATA
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

    _knx_module: KNXModule
    _device: XknxRawValue | XknxExposeSensor
    _payload: Any
    _reset_after: float | None = None
    _reset_device: XknxRawValue | XknxExposeSensor | None = None
    _reset_payload: Any = None
    _reset_task: asyncio.Task[None] | None = None

    @override
    async def async_press(self) -> None:
        """Press the button."""
        if self._reset_task is not None and not self._reset_task.done():
            self._reset_task.cancel()
        await self._device.set(self._payload)
        if self._reset_device is not None and self._reset_after is not None:
            self._reset_task = self._knx_module.entry.async_create_background_task(
                self.hass,
                self._async_reset(),
                f"knx button reset {self.entity_id}",
            )

    async def _async_reset(self) -> None:
        """Reset the button after the configured delay."""
        assert self._reset_device is not None
        assert self._reset_after is not None
        task = asyncio.current_task()
        try:
            await sleep(self._reset_after)
            await self._reset_device.set(self._reset_payload)
        finally:
            if self._reset_task is task:
                self._reset_task = None

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending reset task when removed."""
        if self._reset_task is not None:
            self._reset_task.cancel()
            self._reset_task = None
        await super().async_will_remove_from_hass()


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
            unique_id=build_yaml_unique_id(
                self._device.remote_value.group_address, self._payload
            ),
            entity_config=config,
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
        name = config[CONF_ENTITY][CONF_NAME]
        group_address = knx_conf.get_write(CONF_GA_SEND)
        assert group_address is not None
        dpt_string = knx_conf.get_dpt(CONF_GA_SEND)
        self._device, self._payload = _ui_button_writer(
            knx_module=knx_module,
            name=name,
            group_address=group_address,
            dpt_string=dpt_string,
            button_data=button_data,
        )

        reset_after = knx_conf.get(CONF_RESET_AFTER)
        if reset_after is not None and (reset_data := knx_conf.get(CONF_RESET_DATA)):
            self._reset_after = reset_after
            self._reset_device, self._reset_payload = _ui_button_writer(
                knx_module=knx_module,
                name=name,
                group_address=group_address,
                dpt_string=dpt_string,
                button_data=reset_data,
            )

        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )


def _ui_button_writer(
    knx_module: KNXModule,
    name: str,
    group_address: str,
    dpt_string: str | None,
    button_data: dict[str, Any],
) -> tuple[XknxRawValue | XknxExposeSensor, Any]:
    """Return an XKNX device and payload for a UI-configured button write."""
    if CONF_PAYLOAD in button_data and CONF_PAYLOAD_LENGTH in button_data:
        return (
            XknxRawValue(
                xknx=knx_module.xknx,
                name=name,
                payload_length=button_data[CONF_PAYLOAD_LENGTH],
                group_address=group_address,
            ),
            int(button_data[CONF_PAYLOAD], 16),
        )

    return (
        XknxExposeSensor(
            xknx=knx_module.xknx,
            name=name,
            value_type=dpt_string,
            group_address=group_address,
            respond_to_read=False,
        ),
        button_data[CONF_VALUE],
    )
