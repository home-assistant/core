"""Config flow for Lutron Caseta."""
import logging

from pylutron_caseta.pairing import PAIR_CA, PAIR_CERT, PAIR_KEY, pair
from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.storage import STORAGE_DIR

from . import DOMAIN  # pylint: disable=unused-import
from .const import (
    ABORT_REASON_ALREADY_CONFIGURED,
    ABORT_REASON_CANNOT_CONNECT,
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    ERROR_CANNOT_CONNECT,
    STEP_IMPORT_FAILED,
)

HOSTNAME = "hostname"


FILE_MAPPING = {
    PAIR_KEY: CONF_KEYFILE,
    PAIR_CERT: CONF_CERTFILE,
    PAIR_CA: CONF_CA_CERTS,
}

_LOGGER = logging.getLogger(__name__)

ENTRY_DEFAULT_TITLE = "Caséta bridge"

DATA_SCHEMA_USER = vol.Schema({vol.Required(CONF_HOST): str})


class LutronCasetaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Lutron Caseta config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize a Lutron Caseta flow."""
        self.data = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.data[CONF_HOST] = user_input[CONF_HOST]
            return await self.async_step_link()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA_USER)

    async def async_step_zeroconf(self, discovery_info):
        """Handle a flow initialized by zeroconf discovery."""
        hostname = discovery_info.get(HOSTNAME)
        if hostname is None or not hostname.startswith("lutron-"):
            return self.async_abort(reason="not_lutron_device")

        lutron_id = hostname.split("-")[1]
        if lutron_id.endswith(".local."):
            lutron_id = lutron_id[:-7]

        await self.async_set_unique_id(lutron_id)
        host = discovery_info[CONF_HOST]
        self._abort_if_unique_id_configured({CONF_HOST: host})
        self.data[CONF_HOST] = host

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {CONF_NAME: lutron_id}
        return await self.async_step_link()

    async_step_homekit = async_step_zeroconf

    async def async_step_link(self, user_input=None):
        """Handle pairing with the hub."""
        errors = {}

        if user_input is not None:
            assets = None
            try:
                assets = await self.hass.async_add_executor_job(
                    pair, self.data[CONF_HOST]
                )
            except OSError:
                errors["base"] = "cannot_connect"

            if not errors:
                await self.hass.async_add_executor_job(self._write_tls_assets, assets)

                if await self.async_validate_connectable_bridge_config():
                    return self.async_create_entry(
                        title=self.data[CONF_HOST], data=self.data
                    )

                errors["base"] = "pairing_failed"

        return self.async_show_form(
            step_id="link",
            errors=errors,
            description_placeholders={CONF_HOST: self.data[CONF_HOST]},
        )

    def _write_tls_assets(self, assets):
        """Write the tls assets to disk."""
        host = self.data[CONF_HOST]

        for asset_key, conf_key in FILE_MAPPING.items():
            target_file = self.hass.config.path(
                STORAGE_DIR, f"lutron_caseta-{host}-{asset_key}.pem"
            )
            with open(target_file, "w") as fh:
                fh.write(assets[asset_key])
            self.data[conf_key] = target_file

    async def async_step_import(self, import_info):
        """Import a new Caseta bridge as a config entry.

        This flow is triggered by `async_setup`.
        """

        # Abort if existing entry with matching host exists.
        host = import_info[CONF_HOST]
        if any(
            host == entry.data[CONF_HOST] for entry in self._async_current_entries()
        ):
            return self.async_abort(reason=ABORT_REASON_ALREADY_CONFIGURED)

        # Store the imported config for other steps in this flow to access.
        self.data[CONF_HOST] = host
        self.data[CONF_KEYFILE] = import_info[CONF_KEYFILE]
        self.data[CONF_CERTFILE] = import_info[CONF_CERTFILE]
        self.data[CONF_CA_CERTS] = import_info[CONF_CA_CERTS]

        if not await self.async_validate_connectable_bridge_config():
            # Ultimately we won't have a dedicated step for import failure, but
            # in order to keep configuration.yaml-based configs transparently
            # working without requiring further actions from the user, we don't
            # display a form at all before creating a config entry in the
            # default case, so we're only going to show a form in case the
            # import fails.
            # This will change in an upcoming release where UI-based config flow
            # will become the default for the Lutron Caseta integration (which
            # will require users to go through a confirmation flow for imports).
            return await self.async_step_import_failed()

        return self.async_create_entry(title=ENTRY_DEFAULT_TITLE, data=self.data)

    async def async_step_import_failed(self, user_input=None):
        """Make failed import surfaced to user."""

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {CONF_NAME: self.data[CONF_HOST]}

        if user_input is None:
            return self.async_show_form(
                step_id=STEP_IMPORT_FAILED,
                description_placeholders={"host": self.data[CONF_HOST]},
                errors={"base": ERROR_CANNOT_CONNECT},
            )

        return self.async_abort(reason=ABORT_REASON_CANNOT_CONNECT)

    async def async_validate_connectable_bridge_config(self):
        """Check if we can connect to the bridge with the current config."""

        try:
            bridge = Smartbridge.create_tls(
                hostname=self.data[CONF_HOST],
                keyfile=self.hass.config.path(self.data[CONF_KEYFILE]),
                certfile=self.hass.config.path(self.data[CONF_CERTFILE]),
                ca_certs=self.hass.config.path(self.data[CONF_CA_CERTS]),
            )

            await bridge.connect()
            if not bridge.is_connected():
                return False

            await bridge.close()
            return True
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown exception while checking connectivity to bridge %s",
                self.data[CONF_HOST],
            )
            return False
