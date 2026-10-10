"""KNX configuration storage for entity state exposes."""

from dataclasses import dataclass
from typing import Annotated, Any, NotRequired, TypedDict

import probatio
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
from . import knx_selector
from .entity_store_validation import validate_config_store_data
from .knx_selector import GroupAddressConfig


class KNXExposeStoreOptionModel(TypedDict):
    """Represent KNX entity state expose configuration for an entity."""

    ga: dict[str, Any]  # group address configuration with write and dpt
    attribute: NotRequired[str]
    cooldown: NotRequired[float]
    default: NotRequired[Any]
    send_on_init: NotRequired[bool]
    periodic_send: NotRequired[float]
    respond_to_read: NotRequired[bool]
    value_template: NotRequired[str]


class KNXExposeStoreConfigModel(TypedDict):
    """Represent stored KNX expose configuration with metadata."""

    options: list[KNXExposeStoreOptionModel]
    notes: NotRequired[str]


type KNXExposeStoreModel = dict[str, KNXExposeStoreConfigModel]  # dict[entity_id: conf]


class KNXExposeDataModel(TypedDict):
    """Represent validated KNX expose data of an update request."""

    entity_id: str
    data: ExposeConfig


def validate_expose_template_no_coerce(value: str) -> str:
    """Validate an expose template without coercing to Template."""
    temp = cv.template(value)  # validate template
    if temp.is_static:
        raise probatio.Invalid(
            "Static templates are not supported."
            " Template should start with '{{'"
            " and end with '}}'"
        )
    return value  # return original string for storage and later template creation


@dataclass(kw_only=True, slots=True)
class ExposeOption:
    """An entity state or attribute sent to a group address."""

    # `knx_selector.ga` - a bare `ga` would resolve to this field
    ga: Annotated[
        GroupAddressConfig,
        knx_selector.ga(
            state=False,
            passive=False,
            write_required=True,
            dpt=["numeric", "enum", "complex", "string"],
        ),
    ]
    attribute: str | None = None
    default: Any = None
    cooldown: Annotated[float, cv.positive_float] = 0  # frontend renders to duration
    send_on_init: bool = False
    periodic_send: Annotated[float, cv.positive_float] = 0
    respond_to_read: bool = True
    value_template: Annotated[
        str | None, probatio.Maybe(validate_expose_template_no_coerce)
    ] = None


@dataclass(kw_only=True, slots=True)
class ExposeConfig:
    """Expose configuration of an entity."""

    options: list[ExposeOption]
    notes: str | None = None


EXPOSE_STORE_SCHEMA = probatio.DataclassSchema(ExposeConfig)

EXPOSE_CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required("entity_id"): selector.EntitySelector(),
        probatio.Required("data"): EXPOSE_STORE_SCHEMA,
    },
    extra=probatio.REMOVE_EXTRA,
)


def validate_expose_data(data: dict) -> KNXExposeDataModel:
    """Validate and convert expose configuration data."""
    return validate_config_store_data(EXPOSE_CONFIG_SCHEMA, data)  # type: ignore[no-any-return]


def validate_stored_expose_config(config: dict) -> ExposeConfig:
    """Validate a stored expose configuration of an entity."""
    return validate_config_store_data(EXPOSE_STORE_SCHEMA, config)


def _to_expose_options(hass: HomeAssistant, option: ExposeOption) -> KnxExposeOptions:
    """Convert a validated expose option to expose options."""
    assert option.ga.write is not None  # write is required
    assert option.ga.dpt is not None  # dpt is required
    dpt: type[DPTBase] = DPTBase.parse_transcoder(option.ga.dpt)  # type: ignore[assignment]
    value_template = None
    if option.value_template is not None:
        value_template = template_helper.Template(option.value_template, hass)
    return KnxExposeOptions(
        group_address=parse_device_group_address(option.ga.write),
        dpt=dpt,
        attribute=option.attribute,
        cooldown=option.cooldown,
        default=option.default,
        send_on_init=option.send_on_init,
        periodic_send=option.periodic_send,
        respond_to_read=option.respond_to_read,
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
        self, hass: HomeAssistant, xknx: XKNX, config: dict[str, ExposeConfig]
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
        expose_config: ExposeConfig,
    ) -> None:
        """Update entity expose configuration for an entity."""
        self.remove_entity_expose(entity_id)

        expose_options = [
            _to_expose_options(hass, option) for option in expose_config.options
        ]
        expose = KnxExposeEntity(hass, xknx, entity_id, expose_options)
        self._entity_exposes[entity_id] = expose
        expose.async_register()

    @callback
    def remove_entity_expose(self, entity_id: str) -> None:
        """Remove entity expose configuration for an entity."""
        if entity_id in self._entity_exposes:
            self._entity_exposes.pop(entity_id).async_remove()
