"""KNX configuration storage for entity state exposes."""

from typing import Any, NotRequired, TypedDict

import voluptuous as vol
from xknx import XKNX
from xknx.dpt import DPTBase
from xknx.telegram.address import parse_device_group_address

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    selector,
    template as template_helper,
)

from ..expose import KnxExposeEntity, KnxExposeOptions
from .entity_store_validation import validate_config_store_data
from .knx_selector import GASelector


class KNXExposeStoreOptionModel(TypedDict):
    """Represent KNX entity state expose configuration for an entity."""

    ga: dict[str, Any]  # group address configuration with write and dpt
    attribute: NotRequired[str]
    cooldown: NotRequired[float]
    default: NotRequired[Any]
    periodic_send: NotRequired[float]
    respond_to_read: NotRequired[bool]
    value_template: NotRequired[str]


class KNXExposeStoreConfigModel(TypedDict):
    """Represent stored KNX expose configuration with metadata."""

    options: list[KNXExposeStoreOptionModel]
    notes: NotRequired[str]


type KNXExposeStoreModel = dict[str, KNXExposeStoreConfigModel]  # dict[entity_id: conf]


class KNXExposeDataModel(TypedDict):
    """Represent a loaded KNX expose config for validation."""

    entity_id: str
    data: KNXExposeStoreConfigModel


def validate_expose_template_no_coerce(value: str) -> str:
    """Validate a value is a valid expose template without coercing it to a Template object."""
    temp = cv.template(value)  # validate template
    if temp.is_static:
        raise vol.Invalid(
            "Static templates are not supported. Template should start with '{{' and end with '}}'"
        )
    return value  # return original string for storage and later template creation


EXPOSE_OPTION_SCHEMA = vol.Schema(
    {
        vol.Required("ga"): GASelector(
            state=False,
            passive=False,
            write_required=True,
            dpt=["numeric", "enum", "complex", "string"],
        ),
        vol.Optional("attribute"): str,
        vol.Optional("default"): object,
        vol.Optional("cooldown"): cv.positive_float,  # frontend renders to duration
        vol.Optional("periodic_send"): cv.positive_float,
        vol.Optional("respond_to_read"): bool,
        vol.Optional("value_template"): validate_expose_template_no_coerce,
    }
)

EXPOSE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): selector.EntitySelector(),
        vol.Required("data"): vol.Schema(
            {
                vol.Required("options"): [EXPOSE_OPTION_SCHEMA],
                vol.Optional("notes"): str,
            }
        ),
    },
    extra=vol.REMOVE_EXTRA,
)


def validate_expose_data(data: dict) -> KNXExposeDataModel:
    """Validate and convert expose configuration data."""
    return validate_config_store_data(EXPOSE_CONFIG_SCHEMA, data)  # type: ignore[return-value]


def _store_to_expose_option(
    hass: HomeAssistant, config: KNXExposeStoreOptionModel
) -> KnxExposeOptions:
    """Convert config store option model to expose options."""
    ga = parse_device_group_address(config["ga"]["write"])
    dpt: type[DPTBase] = DPTBase.parse_transcoder(config["ga"]["dpt"])  # type: ignore[assignment]
    value_template = None
    if (_value_template_config := config.get("value_template")) is not None:
        value_template = template_helper.Template(_value_template_config, hass)
    return KnxExposeOptions(
        group_address=ga,
        dpt=dpt,
        attribute=config.get("attribute"),
        cooldown=config.get("cooldown", 0),
        default=config.get("default"),
        periodic_send=config.get("periodic_send", 0),
        respond_to_read=config.get("respond_to_read", True),
        value_template=value_template,
    )


class ExposeController:
    """Controller class for UI entity exposures."""

    def __init__(self) -> None:
        """Initialize entity expose controller."""
        self._entity_exposes: dict[str, KnxExposeEntity] = {}

    @callback
    def stop(self) -> None:
        """Shutdown entity expose controller."""
        for expose in self._entity_exposes.values():
            expose.async_remove()
        self._entity_exposes.clear()

    @callback
    def start(
        self, hass: HomeAssistant, xknx: XKNX, config: KNXExposeStoreModel
    ) -> None:
        """Update entity expose configuration."""
        if self._entity_exposes:
            self.stop()
        for entity_id, options in config.items():
            self.update_entity_expose(hass, xknx, entity_id, options)

    @callback
    def update_entity_expose(
        self,
        hass: HomeAssistant,
        xknx: XKNX,
        entity_id: str,
        expose_config: KNXExposeStoreConfigModel,
    ) -> None:
        """Update entity expose configuration for an entity."""
        self.remove_entity_expose(entity_id)

        expose_options = [
            _store_to_expose_option(hass, config) for config in expose_config["options"]
        ]
        expose = KnxExposeEntity(hass, xknx, entity_id, expose_options)
        self._entity_exposes[entity_id] = expose
        expose.async_register()

    @callback
    def remove_entity_expose(self, entity_id: str) -> None:
        """Remove entity expose configuration for an entity."""
        if entity_id in self._entity_exposes:
            self._entity_exposes.pop(entity_id).async_remove()
