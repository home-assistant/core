"""Support for Tuya buttons."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DPCode
from .entity import TuyaEntity

# All descriptions can be found here.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BUTTONS: dict[str, tuple[ButtonEntityDescription, ...]] = {
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
        ButtonEntityDescription(
            key=DPCode.RESET_DUSTER_CLOTH,
            translation_key="reset_duster_cloth",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_EDGE_BRUSH,
            translation_key="reset_edge_brush",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_FILTER,
            translation_key="reset_filter",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_MAP,
            translation_key="reset_map",
            entity_category=EntityCategory.CONFIG,
        ),
        ButtonEntityDescription(
            key=DPCode.RESET_ROLL_BRUSH,
            translation_key="reset_roll_brush",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Wake Up Light II
    # Not documented
    "hxd": (
        ButtonEntityDescription(
            key=DPCode.SWITCH_USB6,
            translation_key="snooze",
        ),
    ),
     # Smart Pet Feeder
    # https://developer.tuya.com/en/docs/iot/categorycwwsq?id=Kaiuz2b6vydld
    "cwwsq": ( 
        ButtonEntityDescription(
            key=DPCode.MEAL_PLAN,
            translation_key="meal_plan",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya buttons dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya buttons."""
        entities: list[TuyaButtonEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := BUTTONS.get(device.category):
                entities.extend(
                    TuyaButtonEntity(device, hass_data.manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaButtonEntity(TuyaEntity, ButtonEntity):
    """Tuya Button Device."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: ButtonEntityDescription,
    ) -> None:
        """Init Tuya button."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    def press(self) -> None:
        """Press the button."""
        self._send_command([{"code": self.entity_description.key, "value": True}])
