"""Support for ZhongHong HVAC Controller."""

from typing import Any, override

import voluptuous as vol
from zhong_hong_hvac.hvac import HVAC as ZhongHongHVAC

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PORT,
    UnitOfTemperature,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DeviceAddress, ZhongHongConfigEntry, device_unique_id
from .const import (
    ALL_FAN_MODES,
    BREAKS_IN_HA_VERSION,
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
    FAN_MODE_MAP,
    FAN_MODE_REVERSE_MAP,
    INTEGRATION_TITLE,
    LOGGER,
)

# The gateway serializes everything onto a single socket, so there is nothing
# to gain from issuing commands in parallel.
PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_GATEWAY_ADDRESS, default=DEFAULT_GATEWAY_ADDRESS
        ): cv.positive_int,
    }
)

ZHONG_HONG_MODE_COOL = "cool"
ZHONG_HONG_MODE_HEAT = "heat"
ZHONG_HONG_MODE_DRY = "dry"
ZHONG_HONG_MODE_FAN_ONLY = "fan_only"


MODE_TO_STATE = {
    ZHONG_HONG_MODE_COOL: HVACMode.COOL,
    ZHONG_HONG_MODE_HEAT: HVACMode.HEAT,
    ZHONG_HONG_MODE_DRY: HVACMode.DRY,
    ZHONG_HONG_MODE_FAN_ONLY: HVACMode.FAN_ONLY,
}


def _send_failed(command: str) -> HomeAssistantError:
    """Return the error raised when a command cannot be sent."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="send_command_failed",
        translation_placeholders={"command": command},
    )


def _create_deprecated_yaml_issue(hass: HomeAssistant) -> None:
    """Tell the user their YAML configuration has been imported."""
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


def _create_import_failed_issue(hass: HomeAssistant, reason: str, host: str) -> None:
    """Tell the user which part of their YAML the gateway did not answer."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{reason}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{reason}",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
            "host": host,
        },
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML configuration of the ZhongHong HVAC platform."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config[CONF_PORT],
            CONF_GATEWAY_ADDRESS: config[CONF_GATEWAY_ADDRESS],
        },
    )

    # Only a configuration that made it into an entry may be asked to be
    # removed. Telling the user to delete YAML that was never imported would
    # leave the integration with nothing at all.
    if (
        result["type"] is FlowResultType.ABORT
        and (reason := result["reason"]) != "already_configured"
    ):
        _create_import_failed_issue(hass, reason, config[CONF_HOST])
        return

    _create_deprecated_yaml_issue(hass)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZhongHongConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ZhongHong climate entities from a config entry."""
    async_add_entities(
        ZhongHongClimate(entry, address, device)
        for address, device in entry.runtime_data.devices.items()
    )


class ZhongHongClimate(ClimateEntity):
    """Representation of an air conditioner behind a ZhongHong gateway."""

    _attr_fan_modes = ALL_FAN_MODES
    _attr_hvac_modes = [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.OFF,
    ]
    # The gateway reports every change on its own socket, so there is nothing
    # to poll for.
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        entry: ZhongHongConfigEntry,
        address: DeviceAddress,
        device: ZhongHongHVAC,
    ) -> None:
        """Set up a ZhongHong climate device."""
        self._device = device
        addr_out, addr_in = address
        self._attr_name = f"AC {addr_out}-{addr_in}"
        self._attr_unique_id = device_unique_id(entry, address)

    @override
    async def async_added_to_hass(self) -> None:
        """Take the state the gateway pushes for this air conditioner."""
        self._device.register_update_callback(self._handle_device_update)

    def _handle_device_update(self, device: ZhongHongHVAC) -> None:
        """Handle a state push from the gateway.

        The library writes the new state into the device object before calling
        this, and it does so on its own listener thread, so all that is left is
        to ask for the entity to be written from that thread.
        """
        self.schedule_update_ha_state()

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature the device is set to."""
        return self._device.target_temperature

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, idle."""
        if not self.is_on:
            return HVACMode.OFF
        if (operation := self._device.current_operation) is None:
            return None
        return MODE_TO_STATE.get(operation.lower())

    @property
    def is_on(self) -> bool:
        """Return true if on."""
        return self._device.is_on

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if not (fan_mode := self._device.current_fan_mode):
            return None
        return FAN_MODE_REVERSE_MAP.get(fan_mode, fan_mode)

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.min_temp

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.max_temp

    def _command(self, sent: bool, command: str) -> None:
        """Fail if the command did not go out.

        Nothing is written here on success: the unit reports the state it
        actually reached, which is not always the one it was asked for.
        """
        if not sent:
            raise _send_failed(command)

    @override
    def turn_on(self) -> None:
        """Turn on ac."""
        self._command(self._device.turn_on(), "turn-on")

    @override
    def turn_off(self) -> None:
        """Turn off ac."""
        self._command(self._device.turn_off(), "turn-off")

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._command(self._device.set_temperature(temperature), "temperature")

        if (operation_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self.set_hvac_mode(operation_mode)

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            if self.is_on:
                self.turn_off()
            return

        if not self.is_on:
            self.turn_on()

        self._command(self._device.set_operation_mode(hvac_mode.upper()), "mode")

    @override
    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        mapped_mode = FAN_MODE_MAP.get(fan_mode)
        if not mapped_mode:
            LOGGER.error("Unsupported fan mode: %s", fan_mode)
            return

        self._command(self._device.set_fan_mode(mapped_mode), "fan")
