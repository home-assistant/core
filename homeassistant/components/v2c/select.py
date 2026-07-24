"""Select platform for V2C settings."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, override

from pytrydan import Trydan, TrydanData
from pytrydan.exceptions import TrydanError
from pytrydan.models.trydan import ChargeMode, DynamicPowerMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_CONTRACTED_POWER_ENTITY,
    CONF_POWER_DEVIATION_ENTITY,
    CONF_PV_AVAILABLE,
    DOMAIN,
)
from .coordinator import V2CConfigEntry, V2CUpdateCoordinator
from .entity import V2CBaseEntity

_LOGGER = logging.getLogger(__name__)


def charge_mode_value(value: ChargeMode) -> str:
    """Return the charge mode option value."""
    return value.name.lower()


@dataclass(frozen=True, kw_only=True)
class V2CSelectEntityDescription(SelectEntityDescription):
    """Describes V2C EVSE select entity."""

    current_option_fn: Callable[[TrydanData], str | None]
    options: list[str]
    update_fn: Callable[[Trydan, str], Coroutine[Any, Any, None]]


CHARGE_MODE_OPTIONS = [charge_mode_value(mode) for mode in ChargeMode]
DYNAMIC_POWER_MODE_OPTIONS = [str(mode.value) for mode in DynamicPowerMode]

TRYDAN_SELECTS = (
    V2CSelectEntityDescription(
        key="charge_mode",
        translation_key="charge_mode",
        entity_category=EntityCategory.CONFIG,
        options=CHARGE_MODE_OPTIONS,
        current_option_fn=lambda evse_data: (
            charge_mode_value(evse_data.charge_mode)
            if evse_data.charge_mode is not None
            else None
        ),
        update_fn=lambda evse, option: evse.charge_mode(ChargeMode[option.upper()]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up V2C Trydan select platform."""
    coordinator = config_entry.runtime_data
    data = coordinator.data
    assert data is not None

    async_add_entities(
        V2CSelectEntity(
            coordinator,
            description,
            config_entry.entry_id,
        )
        for description in TRYDAN_SELECTS
        if description.current_option_fn(data) is not None
    )

    if (
        coordinator.config_entry.options.get(CONF_PV_AVAILABLE)
        and data.dynamic_power_mode is not None
    ):
        async_add_entities(
            [
                V2CDynamicPowerModeSelectEntity(
                    coordinator,
                    SelectEntityDescription(
                        key="dynamic_power_mode",
                        translation_key="dynamic_power_mode",
                        entity_category=EntityCategory.CONFIG,
                    ),
                    config_entry.entry_id,
                )
            ]
        )


class V2CSelectEntity(V2CBaseEntity, SelectEntity):
    """Representation of V2C EVSE settings select entity."""

    entity_description: V2CSelectEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CSelectEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C select entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_options = description.options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current charge mode."""
        return self.entity_description.current_option_fn(self.data)

    @override
    async def async_select_option(self, option: str) -> None:
        """Update the setting."""
        await self.entity_description.update_fn(self.coordinator.evse, option)
        await self.coordinator.async_request_refresh()


class V2CDynamicPowerModeSelectEntity(V2CBaseEntity, SelectEntity):
    """Specialized selector for dynamic power mode."""

    _contracted_power_entity: str | None
    _power_deviation_entity: str | None
    _attr_options = DYNAMIC_POWER_MODE_OPTIONS

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: SelectEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C select entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

        self._contracted_power_entity = coordinator.config_entry.options.get(
            CONF_CONTRACTED_POWER_ENTITY
        )
        self._power_deviation_entity = coordinator.config_entry.options.get(
            CONF_POWER_DEVIATION_ENTITY
        )

    async def _contracted_power_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return
        value = round(float(new_state.state))
        try:
            if not (evse_data := self.coordinator.evse.data):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_data"
                )
        except TrydanError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_data"
            ) from err
        if evse_data.dynamic_power_mode not in (
            DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED,
            DynamicPowerMode.TIMED_POWER_ENABLED,
        ):
            try:
                await self.coordinator.evse.contracted_power(value)
            finally:
                await self.coordinator.async_request_refresh()

    async def _power_deviation_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return
        value = round(float(new_state.state))
        try:
            if not (evse_data := self.coordinator.evse.data):
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="no_data"
                )
        except TrydanError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_data"
            ) from err
        if (
            evse_data.dynamic_power_mode
            == DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
        ):
            try:
                await self.coordinator.evse.contracted_power(value)
            finally:
                await self.coordinator.async_request_refresh()

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._contracted_power_entity is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._contracted_power_entity],
                    self._contracted_power_changed,
                )
            )
        if self._power_deviation_entity is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._power_deviation_entity],
                    self._power_deviation_changed,
                )
            )

    async def _get_contracted_power(self, entity_id: str | None) -> int:
        if not entity_id:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_dynamic_power_mode_helper",
            )
        if (state := self.hass.states.get(entity_id)) and state.state not in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return round(float(state.state))

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_state",
            translation_placeholders={"entity_id": entity_id},
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Update the setting."""

        evse = self.coordinator.evse
        mode = DynamicPowerMode(int(option))

        if mode == DynamicPowerMode.TIMED_POWER_ENABLED:
            # The profile will set the contracted power
            await evse.dynamic_power_mode(mode)
        else:
            if mode == DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED:
                contracted_power = await self._get_contracted_power(
                    self._power_deviation_entity
                )
            else:
                contracted_power = await self._get_contracted_power(
                    self._contracted_power_entity
                )
            previous_mode = (
                self.coordinator.data.dynamic_power_mode
                if self.coordinator.data
                else None
            )
            await evse.dynamic_power_mode(mode)
            try:
                # Trigger API cached data refresh so it matches the mode just set because
                # the contracted power validator depends on the mode.
                await evse.get_data()
                await evse.contracted_power(contracted_power)
            except TrydanError as err:
                # The mode was committed but the contracted power could not be
                # applied. Try to restore the previous mode so the charger is not
                # left with the new mode and a value under different semantics.
                if previous_mode is not None:
                    try:
                        await evse.dynamic_power_mode(previous_mode)
                    except TrydanError:
                        _LOGGER.exception(
                            "Failed to roll back dynamic power mode after error"
                        )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="dynamic_power_mode_update_failed",
                ) from err
            finally:
                await self.coordinator.async_request_refresh()
            return

        await self.coordinator.async_request_refresh()

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current dynamic power mode."""
        if self.coordinator.data.dynamic_power_mode is not None:
            return str(self.coordinator.data.dynamic_power_mode.value)
        return None
