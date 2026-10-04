"""Config flow for the BM2 battery monitor integration.

Device validation is deliberately protocol-based rather than name-based.

A device is accepted when either:
1. a recognised Legacy or Enhanced BM2 advertisement is observed, or
2. an active connection exposes FFF4 and produces a valid decryptable BM2
   notification.

Known Bluetooth names are still useful for discovery, but are not themselves
treated as proof that the selected device is a BM2.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any, override

from bluetooth_data_tools import short_address
from bmx_ble.battery import Battery, BatteryConfigurationError, custom_battery_profile
import probatio

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    selector,
)

from .const import (
    BATTERY_TYPES,
    BM_NAMES,
    CONF_BATTERY_TYPE,
    CONF_CUSTOM_BATTERY_CHEMISTRY,
    CONF_CUSTOM_CHARGING_VOLTAGE,
    CONF_CUSTOM_CRITICAL_VOLTAGE,
    CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE,
    CONF_CUSTOM_FLOATING_VOLTAGE,
    CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
    CONF_CUSTOM_LOW_VOLTAGE,
    CONF_CUSTOM_NUMPY_PERCENT,
    CONF_CUSTOM_NUMPY_VOLTS,
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_MODE,
    DEFAULT_BATTERY_TYPE,
    DEFAULT_CUSTOM_BATTERY_CHEMISTRY,
    DEFAULT_CUSTOM_CHARGING_VOLTAGE,
    DEFAULT_CUSTOM_CRITICAL_VOLTAGE,
    DEFAULT_CUSTOM_FIFTY_PERCENT_VOLTAGE,
    DEFAULT_CUSTOM_FLOATING_VOLTAGE,
    DEFAULT_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
    DEFAULT_CUSTOM_LOW_VOLTAGE,
    DEFAULT_RATE_LIMIT,
    DEFAULT_RATE_LIMIT_MODE,
    DOMAIN,
    RATE_LIMIT_MODES,
)
from .validation import async_validate_device

_LOGGER = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    """A Bluetooth device offered by the manual config flow."""

    title: str
    discovery_info: BluetoothServiceInfoBleak


def battery_type_selector() -> SelectSelector:
    """Select a stable battery identifier with translated labels."""
    return SelectSelector(
        SelectSelectorConfig(
            options=BATTERY_TYPES,
            translation_key=CONF_BATTERY_TYPE,
        )
    )


def custom_battery_schema(
    options: Mapping[str, Any],
) -> probatio.Schema:
    """Return the custom battery configuration schema."""
    return probatio.Schema(
        {
            probatio.Required(
                CONF_CUSTOM_BATTERY_CHEMISTRY,
                default=options.get(
                    CONF_CUSTOM_BATTERY_CHEMISTRY,
                    DEFAULT_CUSTOM_BATTERY_CHEMISTRY,
                ),
            ): str,
            probatio.Required(
                CONF_CUSTOM_CRITICAL_VOLTAGE,
                default=options.get(
                    CONF_CUSTOM_CRITICAL_VOLTAGE,
                    DEFAULT_CUSTOM_CRITICAL_VOLTAGE,
                ),
            ): probatio.All(probatio.Coerce(float), probatio.Clamp(min=6.0, max=20.0)),
            probatio.Required(
                CONF_CUSTOM_LOW_VOLTAGE,
                default=options.get(
                    CONF_CUSTOM_LOW_VOLTAGE,
                    DEFAULT_CUSTOM_LOW_VOLTAGE,
                ),
            ): probatio.All(probatio.Coerce(float), probatio.Clamp(min=6.0, max=20.0)),
            probatio.Required(
                CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE,
                default=options.get(
                    CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE,
                    DEFAULT_CUSTOM_FIFTY_PERCENT_VOLTAGE,
                ),
            ): probatio.All(probatio.Coerce(float), probatio.Clamp(min=6.0, max=20.0)),
            probatio.Required(
                CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
                default=options.get(
                    CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
                    DEFAULT_CUSTOM_HUNDRED_PERCENT_VOLTAGE,
                ),
            ): probatio.All(probatio.Coerce(float), probatio.Clamp(min=6.0, max=20.0)),
            probatio.Required(
                CONF_CUSTOM_FLOATING_VOLTAGE,
                default=options.get(
                    CONF_CUSTOM_FLOATING_VOLTAGE,
                    DEFAULT_CUSTOM_FLOATING_VOLTAGE,
                ),
            ): probatio.All(probatio.Coerce(float), probatio.Clamp(min=6.0, max=20.0)),
            probatio.Required(
                CONF_CUSTOM_CHARGING_VOLTAGE,
                default=options.get(
                    CONF_CUSTOM_CHARGING_VOLTAGE,
                    DEFAULT_CUSTOM_CHARGING_VOLTAGE,
                ),
            ): probatio.All(probatio.Coerce(float), probatio.Clamp(min=6.0, max=20.0)),
        }
    )


def process_custom_battery_input(
    user_input: dict[str, Any],
) -> tuple[dict, dict]:
    """Add derived custom battery lookup values, and return errors if required."""

    errors: dict[str, str] = {}

    user_input[CONF_BATTERY_TYPE] = Battery.custom.value
    try:
        profile = custom_battery_profile(
            battery_chemistry=user_input[CONF_CUSTOM_BATTERY_CHEMISTRY],
            critical_voltage=float(user_input[CONF_CUSTOM_CRITICAL_VOLTAGE]),
            low_voltage=float(user_input[CONF_CUSTOM_LOW_VOLTAGE]),
            fifty_percent_voltage=float(user_input[CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE]),
            hundred_percent_voltage=float(
                user_input[CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE]
            ),
            floating_voltage=float(user_input[CONF_CUSTOM_FLOATING_VOLTAGE]),
            charging_voltage=float(user_input[CONF_CUSTOM_CHARGING_VOLTAGE]),
        )
    except BatteryConfigurationError:
        errors["base"] = "custom_voltages_not_in_order"
    else:
        # Preserve the existing storage keys; no NumPy dependency is required.
        user_input[CONF_CUSTOM_NUMPY_VOLTS] = list(profile.volts_to_percent)
        user_input[CONF_CUSTOM_NUMPY_PERCENT] = list(profile.percentages)

    return user_input, errors


class BMxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a BM2 battery monitor."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> BMxOptionsFlow:
        """Get the options flow for this handler."""
        return BMxOptionsFlow()

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_input: dict[str, Any] = {}
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, DiscoveredDevice] = {}

    @staticmethod
    def _bm2_title(address: str) -> str:
        """Return the standard BM2 config-entry title."""
        return f"BM2 battery monitor ({short_address(address)})"

    @staticmethod
    def _manual_device_title(discovery_info: BluetoothServiceInfoBleak) -> str:
        """Return a useful title for an unvalidated manual-selection device."""
        address = discovery_info.address
        name = discovery_info.name

        if not name or name == address:
            return address

        return f"{name} ({address})"

    async def _async_validate_device(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> str:
        """Validate the selected device with the same check used at setup."""
        return await async_validate_device(self.hass, discovery_info)

    @override
    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        validation = await self._async_validate_device(discovery_info)

        if validation == "not_bm2":
            return self.async_abort(reason="not_supported")

        if validation == "cannot_validate":
            return self.async_abort(reason="cannot_validate")

        self._discovery_info = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm a positively validated Bluetooth discovery."""
        assert self._discovery_info is not None

        title = self._bm2_title(self._discovery_info.address)

        if user_input is not None:
            self._user_input = user_input

            options = {CONF_BATTERY_TYPE: self._user_input[CONF_BATTERY_TYPE]}
            del self._user_input[CONF_BATTERY_TYPE]

            if options[CONF_BATTERY_TYPE] == Battery.custom.value:
                self._user_input[CONF_ADDRESS] = self._discovery_info.address
                return await self.async_step_custom_battery_details()

            return self.async_create_entry(
                title=title, data=user_input, options=options
            )

        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders

        data_schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_BATTERY_TYPE,
                    default=DEFAULT_BATTERY_TYPE,
                ): battery_type_selector()
            }
        )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=data_schema,
            description_placeholders=placeholders,
        )

    def _manual_schema(
        self,
        defaults: dict[str, Any] | None = None,
    ) -> probatio.Schema:
        """Build the manual device-selection schema."""
        defaults = defaults or {}

        address_selector = probatio.In(
            {
                address: discovery.title
                for address, discovery in self._discovered_devices.items()
            }
        )

        schema: dict[Any, Any] = {
            probatio.Required(
                CONF_BATTERY_TYPE,
                default=defaults.get(
                    CONF_BATTERY_TYPE,
                    DEFAULT_BATTERY_TYPE,
                ),
            ): battery_type_selector(),
        }

        if CONF_ADDRESS in defaults:
            schema[
                probatio.Required(
                    CONF_ADDRESS,
                    default=defaults[CONF_ADDRESS],
                )
            ] = address_selector
        else:
            schema[probatio.Required(CONF_ADDRESS)] = address_selector

        return probatio.Schema(schema)

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Allow manual selection of any currently discovered BLE device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._user_input = user_input

            await self.async_set_unique_id(
                self._user_input[CONF_ADDRESS], raise_on_progress=False
            )
            self._abort_if_unique_id_configured()

            selected = self._discovered_devices.get(self._user_input[CONF_ADDRESS])

            # The Bluetooth cache can change while the form is open.  Rebuild
            # the list once if the originally selected entry has disappeared.
            if selected is None:
                self._populate_discovered_devices()
                selected = self._discovered_devices.get(self._user_input[CONF_ADDRESS])

            if selected is None:
                errors["base"] = "cannot_validate"
            else:
                validation = await self._async_validate_device(selected.discovery_info)

                if validation in ("valid_passive", "valid_active"):
                    options = {CONF_BATTERY_TYPE: self._user_input[CONF_BATTERY_TYPE]}
                    del self._user_input[CONF_BATTERY_TYPE]

                    if options[CONF_BATTERY_TYPE] == Battery.custom.value:
                        return await self.async_step_custom_battery_details()

                    return self.async_create_entry(
                        title=self._bm2_title(self._user_input[CONF_ADDRESS]),
                        data=self._user_input,
                        options=options,
                    )

                if validation == "not_bm2":
                    errors["base"] = "not_bm2"
                else:
                    errors["base"] = "cannot_validate"

        self._populate_discovered_devices()

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=self._manual_schema(user_input),
            errors=errors,
        )

    async def async_step_custom_battery_details(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle config flow page 2."""
        errors: dict[str, str] = {}

        if user_input is not None:
            options, errors = process_custom_battery_input(user_input)

            if not errors:
                return self.async_create_entry(
                    title=self._bm2_title(self._user_input[CONF_ADDRESS]),
                    data=self._user_input,
                    options=options,
                )

        data_schema = custom_battery_schema(user_input or {})

        return self.async_show_form(
            step_id="custom_battery_details",
            data_schema=data_schema,
            errors=errors,
        )

    def _populate_discovered_devices(self) -> None:
        """Refresh the manually selectable Bluetooth device list."""
        self._discovered_devices.clear()

        current_addresses = self._async_current_ids(include_ignore=False)

        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address

            if address in current_addresses:
                continue

            # Display known-name devices as BM2 candidates, but still validate
            # them after selection.  Everything else remains available because
            # a genuine BM2 may advertise no local name at all.
            if discovery_info.name in BM_NAMES:
                title = self._bm2_title(address)
            else:
                title = self._manual_device_title(discovery_info)

            self._discovered_devices[address] = DiscoveredDevice(
                title=title,
                discovery_info=discovery_info,
            )


class BMxOptionsFlow(OptionsFlowWithReload):
    """Handle BM2 options."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._user_input: dict[str, Any] = {}

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle options flow page 1."""
        if user_input is not None:
            self._user_input = user_input

            if self._user_input[CONF_BATTERY_TYPE] == Battery.custom.value:
                return await self.async_step_custom_battery_details()

            return self.async_create_entry(data=self._user_input)

        data_schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_BATTERY_TYPE,
                    default=self.config_entry.options.get(
                        CONF_BATTERY_TYPE, DEFAULT_BATTERY_TYPE
                    ),
                ): battery_type_selector(),
                probatio.Required(
                    CONF_RATE_LIMIT_MODE,
                    default=self.config_entry.options.get(
                        CONF_RATE_LIMIT_MODE, DEFAULT_RATE_LIMIT_MODE
                    ),
                ): selector(
                    {
                        "select": {
                            "options": RATE_LIMIT_MODES,
                            "multiple": False,
                            "translation_key": "rate_selector",
                        }
                    }
                ),
                probatio.Required(
                    CONF_RATE_LIMIT,
                    default=self.config_entry.options.get(
                        CONF_RATE_LIMIT, DEFAULT_RATE_LIMIT
                    ),
                ): probatio.All(probatio.Coerce(int), probatio.Range(min=10, max=120)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )

    async def async_step_custom_battery_details(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle options flow page 2."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._user_input |= user_input
            options, errors = process_custom_battery_input(self._user_input)

            if not errors:
                return self.async_create_entry(title="", data=options)

        data_schema = custom_battery_schema(
            self.config_entry.options | self._user_input
        )

        return self.async_show_form(
            step_id="custom_battery_details",
            data_schema=data_schema,
            errors=errors,
        )
