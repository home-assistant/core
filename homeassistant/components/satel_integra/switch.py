"""Support for Satel Integra modifiable outputs represented as switches."""

from typing import Any, override

from satel_integra import (
    SatelCommandRejectedError,
    SatelNoResponseError,
    SatelResultCode,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    DOMAIN,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
)
from .coordinator import SatelConfigEntry, SatelIntegraOutputsCoordinator
from .entity import SatelIntegraEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SatelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Satel Integra switch devices."""

    runtime_data = config_entry.runtime_data

    for subentry in config_entry.get_subentries_of_type(
        SUBENTRY_TYPE_SWITCHABLE_OUTPUT
    ):
        switchable_output_num: int = subentry.data[CONF_SWITCHABLE_OUTPUT_NUMBER]

        async_add_entities(
            [
                SatelIntegraSwitch(
                    runtime_data.coordinator_outputs,
                    config_entry.entry_id,
                    subentry,
                    switchable_output_num,
                    config_entry.options.get(CONF_CODE),
                ),
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SatelIntegraSwitch(
    SatelIntegraEntity[SatelIntegraOutputsCoordinator], SwitchEntity
):
    """Representation of an Satel Integra switch."""

    _attr_name = None

    def __init__(
        self,
        coordinator: SatelIntegraOutputsCoordinator,
        config_entry_id: str,
        subentry: ConfigSubentry,
        device_number: int,
        code: str | None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator,
            config_entry_id,
            subentry,
            device_number,
        )

        self._code = code

        self._attr_is_on = self._get_state_from_coordinator()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._get_state_from_coordinator()
        self.async_write_ha_state()

    def _get_state_from_coordinator(self) -> bool | None:
        """Method to get switch state from coordinator data."""
        return self.coordinator.data.get(self._device_number)

    async def _async_set_output(self, state: bool) -> None:
        """Set the output state and validate the result returned by the panel."""
        if self._code is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_output_access_code",
            )

        try:
            await self._controller.set_output(
                self._code,
                self._device_number,
                state,
                wait_for_result=True,
            )
        except SatelCommandRejectedError as err:
            if err.result.code is SatelResultCode.USER_CODE_NOT_FOUND:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="command_invalid_access_code",
                ) from err
            if err.result.code is SatelResultCode.NO_ACCESS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="command_no_access",
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={
                    "result_code": f"0x{int(err.result.code):02X}"
                },
            ) from err
        except SatelNoResponseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_outcome_unknown",
            ) from err

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._async_set_output(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._async_set_output(False)
        self._attr_is_on = False
        self.async_write_ha_state()
