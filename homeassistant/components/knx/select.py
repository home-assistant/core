"""Support for KNX select entities."""

from typing import Any, override

from xknx.devices import RawValue

from homeassistant import config_entries
from homeassistant.components.select import SelectEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIONS,
    CONF_PAYLOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_PAYLOAD_LENGTH,
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
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
from .schema import SelectSchema
from .storage.const import CONF_ENTITY, CONF_GA_SELECT, CONF_OPTION
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.SELECT,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiSelect,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.SELECT):
        entities.extend(
            KnxYamlSelect(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.SELECT):
        entities.extend(
            KnxUiSelect(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxSelect(SelectEntity, RestoreEntity):
    """Representation of a KNX select."""

    _device: RawValue
    _option_payloads: dict[str, int]

    def init_base(self) -> None:
        """Initialize attributes shared by the YAML and UI variants."""
        self._attr_options = list(self._option_payloads)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the option the current payload is assigned to."""
        return self.option_from_payload(self._device.remote_value.value)

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if (
                last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                and (payload := self._option_payloads.get(last_state.state)) is not None
            ):
                self._device.remote_value.update_value(payload)

    def option_from_payload(self, payload: int | None) -> str | None:
        """Return the option a given payload is assigned to."""
        try:
            return next(
                key for key, value in self._option_payloads.items() if value == payload
            )
        except StopIteration:
            return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        payload = self._option_payloads[option]
        await self._device.set(payload)


class KnxYamlSelect(_KnxSelect, KnxYamlEntity):
    """Representation of a KNX select configured from YAML."""

    _device: RawValue

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX select."""
        self._device = RawValue(
            knx_module.xknx,
            name=config[CONF_NAME],
            payload_length=config[CONF_PAYLOAD_LENGTH],
            group_address=config[KNX_ADDRESS],
            group_address_state=config.get(CONF_STATE_ADDRESS),
            respond_to_read=config[CONF_RESPOND_TO_READ],
            sync_state=config[CONF_SYNC_STATE],
        )
        super().__init__(
            knx_module=knx_module,
            unique_id=build_yaml_unique_id(self._device.remote_value.group_address),
            entity_config=config,
        )
        self._option_payloads = {
            option[SelectSchema.CONF_OPTION]: option[CONF_PAYLOAD]
            for option in config[SelectSchema.CONF_OPTIONS]
        }
        self.init_base()


class KnxUiSelect(_KnxSelect, KnxUiEntity):
    """Representation of a KNX select configured from the UI."""

    _device: RawValue

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize a KNX select."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = RawValue(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            payload_length=knx_conf.get(CONF_PAYLOAD_LENGTH),
            group_address=knx_conf.get_write(CONF_GA_SELECT),
            group_address_state=knx_conf.get_state_and_passive(CONF_GA_SELECT),
            respond_to_read=knx_conf.get(CONF_RESPOND_TO_READ),
            sync_state=knx_conf.get(CONF_SYNC_STATE),
        )
        self._option_payloads = {
            option[CONF_OPTION]: option[CONF_PAYLOAD]
            for option in knx_conf.get(CONF_OPTIONS)
        }
        self.init_base()
