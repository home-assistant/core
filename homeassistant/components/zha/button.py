"""Support for ZHA button."""
from __future__ import annotations

import abc
import functools
import logging
from typing import TYPE_CHECKING, Any, Self

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import CLUSTER_HANDLER_IDENTIFY, DATA_ZHA, SIGNAL_ADD_ENTITIES
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice


MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.BUTTON)
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.BUTTON
)
DEFAULT_DURATION = 5  # seconds

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation button from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.BUTTON]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAButton(ZhaEntity, ButtonEntity):
    """Defines a ZHA button."""

    _command_name: str

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this button."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._cluster_handler: ClusterHandler = cluster_handlers[0]

    @abc.abstractmethod
    def get_args(self) -> list[Any]:
        """Return the arguments to use in the command."""

    async def async_press(self) -> None:
        """Send out a update command."""
        command = getattr(self._cluster_handler, self._command_name)
        arguments = self.get_args()
        await command(*arguments)


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_IDENTIFY)
class ZHAIdentifyButton(ZHAButton):
    """Defines a ZHA identify button."""

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> Self | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        if ZHA_ENTITIES.prevent_entity_creation(
            Platform.BUTTON, zha_device.ieee, CLUSTER_HANDLER_IDENTIFY
        ):
            return None
        return cls(unique_id, zha_device, cluster_handlers, **kwargs)

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Identify"
    _command_name = "identify"

    def get_args(self) -> list[Any]:
        """Return the arguments to use in the command."""

        return [DEFAULT_DURATION]


class ZHAAttributeButton(ZhaEntity, ButtonEntity):
    """Defines a ZHA button, which writes a value to an attribute."""

    _attribute_name: str
    _attribute_value: Any = None

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs: Any,
    ) -> None:
        """Init this button."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._cluster_handler: ClusterHandler = cluster_handlers[0]

    async def async_press(self) -> None:
        """Write attribute with defined value."""
        await self._cluster_handler.write_attributes_safe(
            {self._attribute_name: self._attribute_value}
        )
        self.async_write_ha_state()


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
class FrostLockResetButton(ZHAAttributeButton, id_suffix="reset_frost_lock"):
    """Defines a ZHA frost lock reset button."""

    _attribute_name = "frost_lock_reset"
    _attr_name = "Frost lock reset"
    _attribute_value = 0
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.motion.ac01"}
)
class NoPresenceStatusResetButton(
    ZHAAttributeButton, id_suffix="reset_no_presence_status"
):
    """Defines a ZHA no presence status reset button."""

    _attribute_name = "reset_no_presence_status"
    _attr_name = "Presence status reset"
    _attribute_value = 1
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG


@MULTI_MATCH(cluster_handler_names="opple_cluster", models={"aqara.feeder.acn001"})
class AqaraPetFeederFeedButton(ZHAAttributeButton, id_suffix="feeding"):
    """Defines a feed button for the aqara c1 pet feeder."""

    _attribute_name = "feeding"
    _attr_name = "Feed"
    _attribute_value = 1


@CONFIG_DIAGNOSTIC_MATCH(
    cluster_handler_names="opple_cluster", models={"lumi.sensor_smoke.acn03"}
)
class AqaraSelfTestButton(ZHAAttributeButton, id_suffix="self_test"):
    """Defines a ZHA self-test button for Aqara smoke sensors."""

    _attribute_name = "self_test"
    _attr_name = "Self-test"
    _attribute_value = 1
    _attr_entity_category = EntityCategory.CONFIG
