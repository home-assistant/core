"""Config flow for Harbor."""

from typing import Any, override

from harbor.config import HarborCameraConfig
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers import selector

from .const import CONF_CERT_PEM, CONF_KEY_PEM, CONF_SERIAL, DOMAIN
from .coordinator import async_probe_camera

SERIAL_LENGTH = 10

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL): selector.TextSelector(selector.TextSelectorConfig()),
        vol.Required(CONF_CERT_PEM): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        ),
        vol.Required(CONF_KEY_PEM): selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        ),
        vol.Required(CONF_IP_ADDRESS): selector.TextSelector(
            selector.TextSelectorConfig()
        ),
    }
)


def _validate_serial(value: str) -> bool:
    """Validate the Harbor serial number."""
    return len(value) == SERIAL_LENGTH and value.isdigit()


def _validate_cert_pem(value: str) -> bool:
    """Validate a Harbor client certificate PEM blob."""
    value = value.strip()
    return value.startswith("-----BEGIN CERTIFICATE-----") and value.endswith(
        "-----END CERTIFICATE-----"
    )


def _validate_key_pem(value: str) -> bool:
    """Validate a Harbor private key PEM blob."""
    value = value.strip()
    return value.startswith("-----BEGIN PRIVATE KEY-----") and value.endswith(
        "-----END PRIVATE KEY-----"
    )


def _validate_credentials(cert_pem: str, key_pem: str) -> dict[str, str]:
    """Validate cert/key PEM blobs and return any errors."""
    errors: dict[str, str] = {}
    if not _validate_cert_pem(cert_pem):
        errors[CONF_CERT_PEM] = "invalid_cert"
    if not _validate_key_pem(key_pem):
        errors[CONF_KEY_PEM] = "invalid_key"
    return errors


class HarborConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Harbor."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_SCHEMA,
                errors={},
            )

        normalized = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in user_input.items()
        }
        errors: dict[str, str] = {}
        display_name: str | None = None

        serial = normalized[CONF_SERIAL]
        if not _validate_serial(serial):
            errors[CONF_SERIAL] = "invalid_serial"

        errors.update(
            _validate_credentials(normalized[CONF_CERT_PEM], normalized[CONF_KEY_PEM])
        )

        if not errors:
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()

            config = HarborCameraConfig(
                serial=serial,
                cert_pem=normalized[CONF_CERT_PEM],
                key_pem=normalized[CONF_KEY_PEM],
                ip_address=normalized[CONF_IP_ADDRESS],
            )
            try:
                display_name = await async_probe_camera(config)
            except TimeoutError:
                errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_SCHEMA,
                errors=errors,
            )

        entry_data: dict[str, Any] = {
            CONF_SERIAL: serial,
            CONF_CERT_PEM: normalized[CONF_CERT_PEM],
            CONF_KEY_PEM: normalized[CONF_KEY_PEM],
            CONF_IP_ADDRESS: normalized[CONF_IP_ADDRESS],
        }

        return self.async_create_entry(
            title=display_name or f"Camera {serial}",
            data=entry_data,
        )
