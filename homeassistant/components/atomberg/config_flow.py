"""Config flow for Atomberg."""

from typing import Any, override

from ha_atomberg_integration import AtombergAuthError, AtombergClient, AtombergError
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_IDS, CONF_REFRESH_TOKEN, DOMAIN, LOGGER

PORTAL_URL = "https://developer.atomberg-iot.com"

CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
        probatio.Required(probatio.Secret(CONF_REFRESH_TOKEN)): cv.string,
    }
)


class AtombergConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atomberg."""

    VERSION = 1

    async def _async_validate(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], set[str]]:
        """Validate the credentials, returning errors and the account's device IDs."""
        client = AtombergClient(
            async_get_clientsession(self.hass),
            user_input[CONF_API_KEY],
            user_input[CONF_REFRESH_TOKEN],
        )
        try:
            devices = await client.async_get_devices()
        except AtombergAuthError:
            return {"base": "invalid_auth"}, set()
        except AtombergError:
            return {"base": "cannot_connect"}, set()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}, set()
        return {}, {device.device_id for device in devices}

    def _known_device_ids(self, entry: ConfigEntry) -> set[str]:
        """Return the device IDs known for a config entry.

        Devices are only registered once the entry has been set up, so the IDs
        saved when the credentials were validated are used as well.
        """
        registered = {
            identifier
            for device in dr.async_entries_for_config_entry(
                dr.async_get(self.hass), entry.entry_id
            )
            for domain, identifier in device.identifiers
            if domain == DOMAIN
        }
        return registered | set(entry.data.get(CONF_DEVICE_IDS, []))

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            self._abort_if_unique_id_configured()
            errors, device_ids = await self._async_validate(user_input)
            if not errors:
                # The API key can be rotated, so also detect an account that is
                # already set up by comparing its devices.
                if any(
                    not device_ids.isdisjoint(self._known_device_ids(entry))
                    for entry in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")
                return self.async_create_entry(
                    title="Atomberg",
                    data={**user_input, CONF_DEVICE_IDS: sorted(device_ids)},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA, user_input
            ),
            description_placeholders={"portal_url": PORTAL_URL},
            errors=errors,
        )
