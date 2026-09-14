"""Viessmann ViCare switch device."""

from contextlib import suppress
import enum
from typing import Any, override

from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareCommandError,
    PyViCareNotSupportedFeatureError,
)
from PyViCare.PyViCareVentilationDevice import (
    VentilationDevice as PyViCareVentilationDevice,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice


class VentilationQuickmode(enum.StrEnum):
    """ViCare ventilation quickmodes that can be switched on and off.

    `standby` is used by the fan entity, `holiday` is scheduled instead of
    activated.
    """

    COMFORT = "comfort"
    ECO = "eco"
    FORCED_LEVEL_FOUR = "forcedLevelFour"
    SILENT = "silent"


# Also used as unique id suffix, so the quickmodes cannot collide with other
# switches that may be added for the same device later on.
ENTITY_KEYS = {
    VentilationQuickmode.COMFORT: "quickmode_comfort",
    VentilationQuickmode.ECO: "quickmode_eco",
    VentilationQuickmode.FORCED_LEVEL_FOUR: "quickmode_forced_level_four",
    VentilationQuickmode.SILENT: "quickmode_silent",
}


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareQuickmodeSwitch]:
    """Create ViCare switch entities for a device."""
    entities: list[ViCareQuickmodeSwitch] = []
    for device in device_list:
        if not device.api.isVentilationDevice():
            continue
        available: list[str] = []
        with suppress(PyViCareNotSupportedFeatureError):
            available = device.api.getVentilationQuickmodes()
        entities.extend(
            ViCareQuickmodeSwitch(quickmode, device.serial, device.config, device.api)
            for quickmode in VentilationQuickmode
            if quickmode in available
        )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ViCare switch entities."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        ),
        # run update to have the current quickmode state on startup
        True,
    )


class ViCareQuickmodeSwitch(ViCareEntity, SwitchEntity):
    """Representation of a ViCare ventilation quickmode."""

    _api: PyViCareVentilationDevice

    def __init__(
        self,
        quickmode: VentilationQuickmode,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareVentilationDevice,
    ) -> None:
        """Initialize the switch."""
        super().__init__(ENTITY_KEYS[quickmode], device_serial, device_config, device)
        self._quickmode = quickmode
        self._attr_translation_key = ENTITY_KEYS[quickmode]

    def update(self) -> None:
        """Update state of the switch."""
        with self.vicare_api_handler(), suppress(PyViCareNotSupportedFeatureError):
            self._attr_is_on = self._api.getVentilationQuickmode(self._quickmode)

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Activate the quickmode."""
        try:
            self._api.activateVentilationQuickmode(self._quickmode)
        except PyViCareCommandError as err:
            # Any failed command lands here, but the one users hit is the
            # device refusing a second quickmode instead of switching over.
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="quickmode_not_activated",
                translation_placeholders={"quickmode": self._quickmode},
            ) from err

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Deactivate the quickmode."""
        self._api.deactivateVentilationQuickmode(self._quickmode)
