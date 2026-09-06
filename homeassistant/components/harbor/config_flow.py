"""Config flow for Harbor."""

from typing import Any, override

from harbor.config import HarborCameraConfig
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_CERT_PEM, CONF_KEY_PEM, CONF_SERIAL, DOMAIN, MODEL
from .coordinator import async_probe_camera

SERIAL_LENGTH = 10
HOSTNAME_PREFIX = "harborc-"

TEXT_SELECTOR = selector.TextSelector(selector.TextSelectorConfig())
PEM_SELECTOR = selector.TextSelector(selector.TextSelectorConfig(multiline=True))

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL): TEXT_SELECTOR,
        vol.Required(CONF_CERT_PEM): PEM_SELECTOR,
        vol.Required(CONF_KEY_PEM): PEM_SELECTOR,
        vol.Required(CONF_IP_ADDRESS): TEXT_SELECTOR,
    }
)

STEP_DISCOVERY_CONFIRM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CERT_PEM): PEM_SELECTOR,
        vol.Required(CONF_KEY_PEM): PEM_SELECTOR,
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

    _discovered_serial: str
    _discovered_ip: str

    async def _async_probe_and_create(
        self, config: HarborCameraConfig, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Create the entry for a reachable camera, or record a connection error."""
        try:
            display_name = await async_probe_camera(config)
        except TimeoutError:
            errors["base"] = "cannot_connect"
            return None

        return self.async_create_entry(
            title=display_name or f"Camera {config.serial}",
            data={
                CONF_SERIAL: config.serial,
                CONF_CERT_PEM: config.cert_pem,
                CONF_KEY_PEM: config.key_pem,
                CONF_IP_ADDRESS: config.ip_address,
            },
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            serial = user_input[CONF_SERIAL].strip()
            cert_pem = user_input[CONF_CERT_PEM].strip()
            key_pem = user_input[CONF_KEY_PEM].strip()

            if not _validate_serial(serial):
                errors[CONF_SERIAL] = "invalid_serial"
            errors.update(_validate_credentials(cert_pem, key_pem))

            if not errors:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()

                if result := await self._async_probe_and_create(
                    HarborCameraConfig(
                        serial=serial,
                        cert_pem=cert_pem,
                        key_pem=key_pem,
                        ip_address=user_input[CONF_IP_ADDRESS].strip(),
                    ),
                    errors,
                ):
                    return result

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a camera discovered on the network."""
        serial = discovery_info.hostname.removeprefix(HOSTNAME_PREFIX)
        if not _validate_serial(serial):
            return self.async_abort(reason="invalid_discovery_info")

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(
            updates={CONF_IP_ADDRESS: discovery_info.ip}
        )

        self._discovered_serial = serial
        self._discovered_ip = discovery_info.ip
        self.context["title_placeholders"] = {"name": f"{MODEL} {serial}"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the credentials for a discovered camera."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cert_pem = user_input[CONF_CERT_PEM].strip()
            key_pem = user_input[CONF_KEY_PEM].strip()
            errors = _validate_credentials(cert_pem, key_pem)

            if not errors:
                if result := await self._async_probe_and_create(
                    HarborCameraConfig(
                        serial=self._discovered_serial,
                        cert_pem=cert_pem,
                        key_pem=key_pem,
                        ip_address=self._discovered_ip,
                    ),
                    errors,
                ):
                    return result

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_DISCOVERY_CONFIRM_SCHEMA, user_input
            ),
            description_placeholders={"serial": self._discovered_serial},
            errors=errors,
        )
