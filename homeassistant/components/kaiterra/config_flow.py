"""Config flow for the Kaiterra integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_data import (
    KaiterraApiAuthError,
    KaiterraApiClient,
    KaiterraApiError,
    KaiterraDeviceNotFoundError,
)
from .const import (
    AVAILABLE_AQI_STANDARDS,
    AVAILABLE_DEVICE_TYPES,
    AVAILABLE_UNITS,
    CONF_AQI_STANDARD,
    CONF_PREFERRED_UNITS,
    DEFAULT_AQI_STANDARD,
    DEFAULT_PREFERRED_UNIT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_TITLE,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=AVAILABLE_DEVICE_TYPES,
                translation_key="device_type",
            )
        ),
        vol.Optional(CONF_NAME): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AQI_STANDARD, default=DEFAULT_AQI_STANDARD): vol.In(
            AVAILABLE_AQI_STANDARDS
        ),
        vol.Optional(
            CONF_PREFERRED_UNITS,
            default=DEFAULT_PREFERRED_UNIT,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=AVAILABLE_UNITS,
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL_SECONDS,
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    }
)


async def _async_validate_device(
    hass,
    api_key: str,
    device_type: str,
    device_id: str,
    aqi_standard: str,
) -> None:
    """Validate that a device can be read."""
    await KaiterraApiClient(
        async_get_clientsession(hass),
        api_key,
        aqi_standard,
    ).async_validate_device(device_type, device_id)


def _subentry_unique_id(device_id: str) -> str:
    """Return a stable subentry unique ID."""
    return device_id


def _subentry_title(device: Mapping[str, Any]) -> str:
    """Return the title for a device subentry."""
    return device.get(CONF_NAME) or device[CONF_DEVICE_ID]


def _subentry_data(device: Mapping[str, Any]) -> ConfigSubentryData:
    """Convert device data into config-subentry payload data."""
    data = {
        CONF_DEVICE_ID: device[CONF_DEVICE_ID],
        CONF_TYPE: device[CONF_TYPE],
    }
    if device.get(CONF_NAME):
        data[CONF_NAME] = device[CONF_NAME]

    return {
        "subentry_type": SUBENTRY_TYPE_DEVICE,
        "title": _subentry_title(device),
        "unique_id": _subentry_unique_id(device[CONF_DEVICE_ID]),
        "data": MappingProxyType(data),
    }


def _scan_interval_to_seconds(value: Any) -> int:
    """Normalize scan interval values to seconds."""
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return int(value)


def _async_sync_import_subentries(
    hass,
    entry: ConfigEntry,
    subentries: list[ConfigSubentryData],
    *,
    remove_missing: bool,
) -> None:
    """Synchronize imported device subentries to match YAML."""
    desired_unique_ids = {subentry_data["unique_id"] for subentry_data in subentries}
    existing_by_unique_id = {
        subentry.unique_id: subentry for subentry in entry.subentries.values()
    }

    if remove_missing:
        for unique_id, subentry in existing_by_unique_id.items():
            if unique_id not in desired_unique_ids:
                hass.config_entries.async_remove_subentry(entry, subentry.subentry_id)

    for subentry_data in subentries:
        unique_id = subentry_data["unique_id"]
        if unique_id in existing_by_unique_id:
            hass.config_entries.async_update_subentry(
                entry,
                existing_by_unique_id[unique_id],
                data=subentry_data["data"],
                title=subentry_data["title"],
            )
            continue

        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title=subentry_data["title"],
                unique_id=unique_id,
                data=subentry_data["data"],
            ),
        )


async def _async_validate_subentries(
    hass,
    api_key: str,
    aqi_standard: str,
    subentries: list[ConfigSubentry],
) -> None:
    """Validate auth against the first readable configured device."""
    if not subentries:
        return

    validator = KaiterraApiClient(
        async_get_clientsession(hass),
        api_key,
        aqi_standard,
    )
    saw_missing_device = False

    for subentry in subentries:
        try:
            await validator.async_validate_device(
                subentry.data[CONF_TYPE],
                subentry.data[CONF_DEVICE_ID],
            )
        except KaiterraApiAuthError:
            raise
        except KaiterraDeviceNotFoundError:
            saw_missing_device = True
            continue
        except KaiterraApiError:
            raise
        else:
            return

    if saw_missing_device:
        return


class KaiterraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kaiterra."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data=user_input,
                options={
                    CONF_AQI_STANDARD: DEFAULT_AQI_STANDARD,
                    CONF_PREFERRED_UNITS: DEFAULT_PREFERRED_UNIT,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_DATA_SCHEMA, user_input
            ),
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import YAML configuration into a parent entry and device subentries."""
        options = {
            CONF_AQI_STANDARD: import_data.get(CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD),
            CONF_PREFERRED_UNITS: import_data.get(
                CONF_PREFERRED_UNITS, DEFAULT_PREFERRED_UNIT
            ),
            CONF_SCAN_INTERVAL: _scan_interval_to_seconds(
                import_data.get(
                    CONF_SCAN_INTERVAL,
                    timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
                )
            ),
        }
        subentries = [
            _subentry_data(device) for device in import_data.get(CONF_DEVICES, [])
        ]

        if existing_entry := next(
            (
                entry
                for entry in self._async_current_entries()
                if entry.source == SOURCE_IMPORT
            ),
            None,
        ):
            self.hass.config_entries.async_update_entry(
                existing_entry,
                data={CONF_API_KEY: import_data[CONF_API_KEY]},
                options=options,
            )
            _async_sync_import_subentries(
                self.hass, existing_entry, subentries, remove_missing=True
            )
            return self.async_abort(reason="already_configured")

        if existing_entry := next(
            (
                entry
                for entry in self._async_current_entries()
                if entry.data.get(CONF_API_KEY) == import_data[CONF_API_KEY]
            ),
            None,
        ):
            self.hass.config_entries.async_update_entry(existing_entry, options=options)
            _async_sync_import_subentries(
                self.hass, existing_entry, subentries, remove_missing=False
            )
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data={CONF_API_KEY: import_data[CONF_API_KEY]},
            options=options,
            subentries=subentries,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the start of a reauthentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API key."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await _async_validate_subentries(
                    self.hass,
                    user_input[CONF_API_KEY],
                    reauth_entry.options.get(CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD),
                    list(reauth_entry.subentries.values()),
                )
            except KaiterraApiAuthError:
                errors["base"] = "invalid_auth"
            except KaiterraApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return KaiterraOptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry types."""
        return {SUBENTRY_TYPE_DEVICE: KaiterraDeviceSubentryFlowHandler}


class KaiterraDeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for Kaiterra device subentries."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a Kaiterra device subentry."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = _subentry_unique_id(user_input[CONF_DEVICE_ID])
            if any(
                subentry.unique_id == unique_id
                for subentry in self._get_entry().subentries.values()
            ):
                return self.async_abort(reason="already_configured")

            try:
                await _async_validate_device(
                    self.hass,
                    self._get_entry().data[CONF_API_KEY],
                    user_input[CONF_TYPE],
                    user_input[CONF_DEVICE_ID],
                    self._get_entry().options.get(
                        CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD
                    ),
                )
            except KaiterraApiAuthError:
                errors["base"] = "invalid_auth"
            except KaiterraDeviceNotFoundError:
                errors["base"] = "device_not_found"
            except KaiterraApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=_subentry_title(user_input),
                    data=user_input,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DEVICE_SCHEMA, user_input),
            errors=errors,
        )


class KaiterraOptionsFlowHandler(OptionsFlow):
    """Handle Kaiterra account options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Kaiterra options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    CONF_AQI_STANDARD: self.config_entry.options.get(
                        CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD
                    ),
                    CONF_PREFERRED_UNITS: self.config_entry.options.get(
                        CONF_PREFERRED_UNITS, DEFAULT_PREFERRED_UNIT
                    ),
                    CONF_SCAN_INTERVAL: self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
                    ),
                },
            ),
        )
