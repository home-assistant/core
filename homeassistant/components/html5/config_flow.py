"""Config flow for the html5 component."""

import binascii
from typing import cast

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid
from py_vapid.utils import b64urlencode
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import homeassistant.helpers.config_validation as cv

from .const import ATTR_VAPID_EMAIL, ATTR_VAPID_PRV_KEY, ATTR_VAPID_PUB_KEY, DOMAIN
from .issues import async_create_html5_issue

EMAIL_REGEX = r"^([a-zA-Z0-9._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})$"


def vapid_generate_private_key():
    """Generate a VAPID private key."""
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    return b64urlencode(
        binascii.unhexlify(f"{private_key.private_numbers().private_value:x}".zfill(64))
    )


def vapid_get_public_key(private_key: str):
    """Get the VAPID public key from a private key."""
    vapid = Vapid.from_string(private_key)
    public_key = cast(ec.EllipticCurvePublicKey, vapid.public_key)
    return b64urlencode(
        public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )


class HTML5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HTML5."""

    def _create_entry(
        self, data: dict[str, str]
    ) -> tuple[dict[str, str], ConfigFlowResult | None]:
        """Create an entry."""
        errors = {}
        flow_result = None
        try:
            cv.matches_regex(EMAIL_REGEX)(data[ATTR_VAPID_EMAIL])
        except vol.Invalid:
            errors[ATTR_VAPID_EMAIL] = "invalid_email"

        if not data.get(ATTR_VAPID_PRV_KEY):
            data[ATTR_VAPID_PRV_KEY] = vapid_generate_private_key()

        # we will always generate the corresponding public key
        try:
            data[ATTR_VAPID_PUB_KEY] = vapid_get_public_key(data[ATTR_VAPID_PRV_KEY])
        except (ValueError, binascii.Error):
            errors[ATTR_VAPID_PRV_KEY] = "invalid_prv_key"

        if not errors:
            config = {
                ATTR_VAPID_EMAIL: data[ATTR_VAPID_EMAIL],
                ATTR_VAPID_PRV_KEY: data[ATTR_VAPID_PRV_KEY],
                ATTR_VAPID_PUB_KEY: data[ATTR_VAPID_PUB_KEY],
            }
            flow_result = self.async_create_entry(title="HTML5", data=config)
        return errors, flow_result

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            errors, flow_result = self._create_entry(user_input)
            if flow_result:
                return flow_result
        else:
            user_input = {}

        return self.async_show_form(
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_VAPID_EMAIL, default=user_input.get(ATTR_VAPID_EMAIL, "")
                    ): str,
                    vol.Optional(ATTR_VAPID_PRV_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config: dict) -> ConfigFlowResult:
        """Handle config import from yaml."""
        _, flow_result = self._create_entry(import_config)
        if not flow_result:
            async_create_html5_issue(self.hass, False)
            return self.async_abort(reason="invalid_config")
        async_create_html5_issue(self.hass, True)
        return flow_result
