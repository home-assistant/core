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
    async_add_entities(
        [
            FoscamGenericSwitch(coordinator, config_entry, IR_SWITCH_DESCRIPTION),
            FoscamGenericSwitch(coordinator, config_entry, FLIP_SWITCH_DESCRIPTION),
            FoscamGenericSwitch(coordinator, config_entry, MIRROR_SWITCH_DESCRIPTION),
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
                getattr(self.coordinator.session, "sleep"), 0
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
