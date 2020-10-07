"""Config flow for Lutron Caseta."""
import logging

from pylutron_caseta.smartbridge import Smartbridge

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

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

_LOGGER = logging.getLogger(__name__)

ENTRY_DEFAULT_TITLE = "Caséta bridge"


class LutronCasetaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Lutron Caseta config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize a Lutron Caseta flow."""
        self.data = {}

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
