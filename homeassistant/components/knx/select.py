"""Support for KNX select entities."""

import logging
from typing import override

from xknx.devices import RawValue
from xknx.dpt import DPTBase, DPTEnum

from homeassistant import config_entries
from homeassistant.components.select import SelectEntity
from homeassistant.const import (
    CONF_NAME,
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
    CONF_VALUE,
    DOMAIN,
    KNX_ADDRESS,
    KNX_MODULE_KEY,
    SelectConf,
)
from .dpt import raw_payload_length
from .entity import (
    KnxUiEntity,
    KnxUiEntityPlatformController,
    KnxYamlEntity,
    build_yaml_unique_id,
)
from .knx_module import KNXModule
from .storage.const import CONF_ENTITY
from .storage.util import ConfigExtractor

_LOGGER = logging.getLogger(__name__)


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
    if ui_config := knx_module.config_store.get_entity_configs(Platform.SELECT):
        entities.extend(
            KnxUiSelect(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


def _payload_from_value(transcoder: type[DPTBase], value: object) -> int:
    """Encode a value to its raw integer payload using the DPT transcoder."""
    return int.from_bytes(
        transcoder.validate_payload(transcoder.to_knx(value)), byteorder="big"
    )


def _options_from_enum_dpt(dpt: str) -> tuple[dict[str, int], int]:
    """Return option payloads and payload length of an enum DPT."""
    transcoder: type[DPTEnum] | None = DPTEnum.parse_transcoder(dpt)
    assert transcoder is not None  # already checked by validation
    option_payloads = {
        member.name.lower(): member.value for member in transcoder.data_type
    }
    return option_payloads, raw_payload_length(transcoder)


def _options_from_custom_config(
    options: list[ConfigType], dpt: str | None
) -> tuple[dict[str, int], int]:
    """Return option payloads and payload length of manually configured options.

    Options are either typed values encoded by the DPT, or raw payloads. All
    options share one payload length - enforced by the entity store schema.
    """
    transcoder: type[DPTBase] | None = (
        DPTBase.parse_transcoder(dpt) if dpt is not None else None
    )
    payload_length = raw_payload_length(transcoder) if transcoder is not None else None
    option_payloads: dict[str, int] = {}
    for option in options:
        name = option[SelectConf.OPTION]
        if CONF_VALUE in option:
            assert transcoder is not None  # typed values require a DPT
            option_payloads[name] = _payload_from_value(transcoder, option[CONF_VALUE])
        else:
            option_payloads[name] = int(option[CONF_PAYLOAD], 16)
            payload_length = option[CONF_PAYLOAD_LENGTH]
    assert payload_length is not None  # set from the DPT or a raw option
    return option_payloads, payload_length


class _KNXSelect(SelectEntity, RestoreEntity):
    """Representation of a KNX select."""

    _device: RawValue
    _option_payloads: dict[str, int]

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if (
                last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                and (option := self._option_payloads.get(last_state.state)) is not None
            ):
                self._device.remote_value.update_value(option)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self.option_from_payload(self._device.remote_value.value)

    def option_from_payload(self, payload: int | None) -> str | None:
        """Return the option a given payload is assigned to."""
        try:
            return next(
                key for key, value in self._option_payloads.items() if value == payload
            )
        except StopIteration:
            if payload is not None:
                _LOGGER.debug(
                    "No option configured for payload %s of %s: %s",
                    payload,
                    self.entity_id,
                    self._device.remote_value.telegram,
                )
            return None

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        payload = self._option_payloads[option]
        await self._device.set(payload)


class KnxYamlSelect(_KNXSelect, KnxYamlEntity):
    """Representation of a KNX select configured via YAML."""

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
            option[SelectConf.OPTION]: option[CONF_PAYLOAD]
            for option in config[SelectConf.OPTIONS]
        }
        self._attr_options = list(self._option_payloads)


class KnxUiSelect(_KNXSelect, KnxUiEntity):
    """Representation of a KNX select configured via the UI."""

    _device: RawValue

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: ConfigType
    ) -> None:
        """Initialize a KNX select."""
        knx_conf = ConfigExtractor(config[DOMAIN])
        source = knx_conf.get(SelectConf.OPTIONS_SOURCE)
        # the group address key tells how options are defined
        if SelectConf.GA_ENUM in source:
            ga_key = SelectConf.GA_ENUM
            dpt = knx_conf.get_dpt(SelectConf.OPTIONS_SOURCE, ga_key)
            assert dpt is not None  # already checked by validation
            self._option_payloads, payload_length = _options_from_enum_dpt(dpt)
        else:
            ga_key = SelectConf.GA_CUSTOM
            self._option_payloads, payload_length = _options_from_custom_config(
                source[SelectConf.CUSTOM_OPTIONS],
                knx_conf.get_dpt(SelectConf.OPTIONS_SOURCE, ga_key),
            )

        self._device = RawValue(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            payload_length=payload_length,
            group_address=knx_conf.get_write(SelectConf.OPTIONS_SOURCE, ga_key),
            group_address_state=knx_conf.get_state_and_passive(
                SelectConf.OPTIONS_SOURCE, ga_key
            ),
            respond_to_read=knx_conf.get(CONF_RESPOND_TO_READ),
            sync_state=knx_conf.get(CONF_SYNC_STATE),
        )
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        self._attr_options = list(self._option_payloads)
