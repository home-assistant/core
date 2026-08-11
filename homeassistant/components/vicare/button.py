"""Viessmann ViCare button device."""

from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import override

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice, ViCareRequiredKeysMixinWithSet
from .utils import is_supported

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViCareButtonEntityDescription(
    ButtonEntityDescription, ViCareRequiredKeysMixinWithSet
):
    """Describes ViCare button entity."""


BUTTON_DESCRIPTIONS: tuple[ViCareButtonEntityDescription, ...] = (
    ViCareButtonEntityDescription(
        key="activate_onetimecharge",
        translation_key="activate_onetimecharge",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        value_setter=lambda api: api.activateOneTimeCharge(),
    ),
    ViCareButtonEntityDescription(
        key="deactivate_onetimecharge",
        translation_key="deactivate_onetimecharge",
        entity_category=EntityCategory.CONFIG,
        value_getter=lambda api: api.getOneTimeCharge(),
        value_setter=lambda api: api.deactivateOneTimeCharge(),
    ),
)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ButtonEntity]:
    """Create ViCare button entities for a device."""

    entities: list[ButtonEntity] = [
        ViCareButton(
            description,
            device.serial,
            device.config,
            device.api,
        )
        for device in device_list
        for description in BUTTON_DESCRIPTIONS
        if is_supported(description.key, description.value_getter, device.api)
    ]

    # The gateway is not a device of its own in Home Assistant, so its reboot
    # button is added to the first device behind it.
    known_gateways: set[str] = set()
    for device in device_list:
        gateway_serial = device.config.getConfig().serial
        if gateway_serial in known_gateways:
            continue
        known_gateways.add(gateway_serial)
        entities.append(
            ViCareRebootGatewayButton(device.serial, device.config, device.api)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ViCare button entities."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareButton(ViCareEntity, ButtonEntity):
    """Representation of a ViCare button."""

    entity_description: ViCareButtonEntityDescription

    def __init__(
        self,
        description: ViCareButtonEntityDescription,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the button."""
        super().__init__(description.key, device_serial, device_config, device)
        self.entity_description = description

    @override
    def press(self) -> None:
        """Handle the button press."""
        with self.vicare_api_handler(), suppress(PyViCareNotSupportedFeatureError):
            self.entity_description.value_setter(self._api)


class ViCareRebootGatewayButton(ViCareEntity, ButtonEntity):
    """Representation of a button rebooting the ViCare gateway."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reboot_gateway"

    def __init__(
        self,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the button."""
        super().__init__("reboot_gateway", device_serial, device_config, device)
        self._device = device

    @override
    def press(self) -> None:
        """Handle the button press."""
        with self.vicare_api_handler():
            self._device.service.reboot_gateway(self._device.accessor)
