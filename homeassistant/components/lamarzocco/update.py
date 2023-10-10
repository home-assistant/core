"""Support for La Marzocco Switches."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)

from .const import DOMAIN, MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription
from .lm_client import LaMarzoccoClient


@dataclass
class LaMarzoccoUpdateEntityDescriptionMixin:
    """Description of an La Marzocco Update"""
    current_fw_fn: Callable[[LaMarzoccoClient], str]
    latest_fw_fn: Callable[[LaMarzoccoClient], str]


@dataclass
class LaMarzoccoUpdateEntityDescription(
    UpdateEntityDescription,
    LaMarzoccoEntityDescription,
    LaMarzoccoUpdateEntityDescriptionMixin
):
    """Description of an La Marzocco Switch"""


ENTITIES: tuple[LaMarzoccoUpdateEntityDescription, ...] = (
    LaMarzoccoUpdateEntityDescription(
        key="machine_firmware",
        translation_key="machine_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        icon="mdi:cloud-download",
        current_fw_fn=lambda client: client._firmware.get("machine_firmware", {}).get("version", "Unknown"),
        latest_fw_fn=lambda client: client._firmware.get("machine_firmware", {}).get("targetVersion", "Unknown"),
        extra_attributes={
            MODEL_GS3_AV: None,
            MODEL_GS3_MP: None,
            MODEL_LM: None,
            MODEL_LMU: None,
        },
    ),
    LaMarzoccoUpdateEntityDescription(
        key="gateway_firmware",
        translation_key="gateway_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        icon="mdi:cloud-download",
        current_fw_fn=lambda client: client._firmware.get("gateway_firmware", {}).get("version", "Unknown"),
        latest_fw_fn=lambda client: client._firmware.get("gateway_firmware", {}).get("targetVersion", "Unknown"),
        extra_attributes={
            MODEL_GS3_AV: None,
            MODEL_GS3_MP: None,
            MODEL_LM: None,
            MODEL_LMU: None,
        },
    )
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up update entities and services."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        LaMarzoccoUpdateEntity(coordinator, hass, description)
        for description in ENTITIES
        if coordinator.lm.model_name in description.extra_attributes.keys()
    )


class LaMarzoccoUpdateEntity(LaMarzoccoEntity, UpdateEntity):
    """Entity representing the update state"""

    def __init__(self, coordinator, hass, entity_description):
        """Initialise switches."""
        super().__init__(coordinator, hass, entity_description)

    @property
    def installed_version(self):
        """Return the current firmware version."""
        return self.entity_description.current_fw_fn(self._lm_client)

    @property
    def available_version(self):
        """Return the latest firmware version."""
        return self.entity_description.latest_fw_fn(self._lm_client)
