"""Component provides support for the Foscam Switch."""

from __future__ import annotations

from typing import Any

from coordinator import FoscamConfigEntry, FoscamCoordinator
from entity import FoscamEntity

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

FLIP_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_Flip",
    name="Flip Switch",
    icon="mdi:flip-vertical",
)

MIRROR_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_Mirror",
    name="Mirror Switch",
    icon="mdi:mirror",
)

IR_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_openIr",
    name="Ir switch",
    icon="mdi:theme-light-dark",
)

SLEEP_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_asleep",
    name="sleep switch",
    icon="mdi:sleep",
)

WHITE_LIGHT_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_openWhiteLight",
    name="WhiteLight switch",
    icon="mdi:light-flood-down",
)

SIREN_ALARM_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_sirenalarm",
    name="SirenAlarm switch",
    icon="mdi:alarm-note",
)

TURN_OFF_VOLUME_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_TurnOffVolume",
    name="TurnOffVolume switch",
    icon="mdi:volume-off",
)

LIGHT_STATUS_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_TurnOffLight",
    name="TurnOffLight switch",
    icon="mdi:lightbulb-fluorescent-tube",
)

HDR_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_OpenHdr",
    name="Hdr switch",
    icon="mdi:hdr",
)

WDR_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="is_OpenWdr",
    name="Wdr switch",
    icon="mdi:alpha-w-box",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up foscam switch from a config entry."""

    coordinator = config_entry.runtime_data
    await coordinator.async_config_entry_first_refresh()

    if coordinator.data["is_asleep"]["supported"]:
        async_add_entities(
            [FoscamGenericSwitch(coordinator, config_entry, SLEEP_SWITCH_DESCRIPTION)]
        )
    if ((1 << 8) & int(coordinator.data["product_info"]["reserve3"])) != 0:
        async_add_entities(
            [FoscamGenericSwitch(coordinator, config_entry, WDR_SWITCH_DESCRIPTION)]
        )
    else:
        async_add_entities(
            [FoscamGenericSwitch(coordinator, config_entry, HDR_SWITCH_DESCRIPTION)]
        )
    async_add_entities(
        [
            FoscamGenericSwitch(coordinator, config_entry, IR_SWITCH_DESCRIPTION),
            FoscamGenericSwitch(coordinator, config_entry, FLIP_SWITCH_DESCRIPTION),
            FoscamGenericSwitch(coordinator, config_entry, MIRROR_SWITCH_DESCRIPTION),
            FoscamGenericSwitch(
                coordinator, config_entry, WHITE_LIGHT_SWITCH_DESCRIPTION
            ),
            FoscamGenericSwitch(
                coordinator, config_entry, SIREN_ALARM_SWITCH_DESCRIPTION
            ),
            FoscamGenericSwitch(
                coordinator, config_entry, TURN_OFF_VOLUME_SWITCH_DESCRIPTION
            ),
            FoscamGenericSwitch(
                coordinator, config_entry, LIGHT_STATUS_SWITCH_DESCRIPTION
            ),
        ]
    )


class FoscamGenericSwitch(FoscamEntity, SwitchEntity):
    """A generic switch class for Foscam entities."""

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        config_entry: FoscamConfigEntry,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the generic switch."""
        super().__init__(coordinator, config_entry.entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        if self.entity_description.key == "is_asleep":
            self._state = self.coordinator.data["is_asleep"]["status"]
        else:
            self._state = self.coordinator.data.get(self.entity_description.key, False)

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        if int(self._state) == 0:
            return False
        return True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        if self.entity_description.key == "is_Flip":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "flip_video"), 0
            )
        elif self.entity_description.key == "is_Mirror":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "mirror_video"), 0
            )
        elif self.entity_description.key == "is_openIr":
            ret, _ = await self.hass.async_add_executor_job(
                self.coordinator.session.set_infra_led_config, 0
            )
            ret, _ = await self.hass.async_add_executor_job(
                self.coordinator.session.open_infra_led
            )
        elif self.entity_description.key == "is_asleep":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "wake_up"), 0
            )
        elif self.entity_description.key == "is_openWhiteLight":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "closeWhiteLight")
            )
        elif self.entity_description.key == "is_sirenalarm":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setSirenConfig"), 0, 100, 0
            )
        elif self.entity_description.key == "is_TurnOffVolume":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setVoiceEnableState"), 1
            )
        elif self.entity_description.key == "is_TurnOffLight":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setLedEnableState"), 1
            )
        elif self.entity_description.key == "is_OpenWdr":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setWdrMode"), 0
            )
        elif self.entity_description.key == "is_OpenHdr":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setHdrMode"), 0
            )
        if ret != 0:
            raise HomeAssistantError(f"Error turning off: {ret}")
        self._state = False
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the entity."""
        if self.entity_description.key == "is_Flip":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "flip_video"), 1
            )
        elif self.entity_description.key == "is_Mirror":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "mirror_video"), 1
            )
        elif self.entity_description.key == "is_openIr":
            ret, _ = await self.hass.async_add_executor_job(
                self.coordinator.session.set_infra_led_config, 1
            )
            ret, _ = await self.hass.async_add_executor_job(
                self.coordinator.session.open_infra_led
            )
        elif self.entity_description.key == "is_asleep":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "sleep")
            )
        elif self.entity_description.key == "is_openWhiteLight":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "openWhiteLight")
            )
        elif self.entity_description.key == "is_sirenalarm":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setSirenConfig"), 1, 100, 0
            )
        elif self.entity_description.key == "is_TurnOffVolume":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setVoiceEnableState"), 0
            )
        elif self.entity_description.key == "is_TurnOffLight":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setLedEnableState"), 0
            )
        elif self.entity_description.key == "is_OpenWdr":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setWdrMode"), 1
            )
        elif self.entity_description.key == "is_OpenHdr":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setHdrMode"), 1
            )
        if ret != 0:
            raise HomeAssistantError(f"Error turning on: {ret}")
        self._state = True
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.key == "is_asleep":
            self._state = self.coordinator.data["is_asleep"]["status"]
        else:
            self._state = self.coordinator.data.get(self.entity_description.key, False)
        self.async_write_ha_state()
