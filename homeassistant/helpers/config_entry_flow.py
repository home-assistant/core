"""Helpers for data entry flows for config entries."""
from functools import partial

from homeassistant.core import callback
from homeassistant import config_entries, data_entry_flow


def register_discovery_flow(domain, title, discovery_function):
    """Register flow for discovered integrations that not require auth."""
    config_entries.HANDLERS.register(domain)(
        partial(DiscoveryFlowHandler, domain, title, discovery_function))


class DiscoveryFlowHandler(data_entry_flow.FlowHandler):
    """Handle a discovery config flow."""

    VERSION = 1

    def __init__(self, domain, title, discovery_function):
        """Initialize the discovery config flow."""
        self._domain = domain
        self._title = title
        self._discovery_function = discovery_function

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(
                reason='single_instance_allowed'
            )

        # Get current discovered entries.
        in_progress = self._async_in_progress()

        has_devices = in_progress
        if not has_devices:
            has_devices = await self.hass.async_add_job(
                self._discovery_function, self.hass)

        if not has_devices:
            return self.async_abort(
                reason='no_devices_found'
            )

        # Cancel the discovered one.
        for flow in in_progress:
            self.hass.config_entries.flow.async_abort(flow['flow_id'])

        return self.async_create_entry(
            title=self._title,
            data={},
        )

    async def async_step_confirm(self, user_input=None):
        """Confirm setup."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data={},
            )

        return self.async_show_form(
            step_id='confirm',
        )

    async def async_step_discovery(self, discovery_info):
        """Handle a flow initialized by discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(
                reason='single_instance_allowed'
            )

        return await self.async_step_confirm()

    async def async_step_import(self, _):
        """Handle a flow initialized by import."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(
                reason='single_instance_allowed'
            )

        return self.async_create_entry(
            title=self._title,
            data={},
        )

    @callback
    def _async_current_entries(self):
        """Return current entries."""
        return self.hass.config_entries.async_entries(self._domain)

    @callback
    def _async_in_progress(self):
        """Return other in progress flows for current domain."""
        return [flw for flw in self.hass.config_entries.flow.async_progress()
                if flw['handler'] == self._domain and
                flw['flow_id'] != self.flow_id]
