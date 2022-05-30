"""Support for proxy services."""
import asyncio

import voluptuous as vol
from homeassistant.core import SERVICE_CALL_LIMIT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import SERVICE_DESCRIPTION_CACHE

from .const import CONF_SERVICE_PREFIX, CONF_SERVICES


class ProxyServices:
    """Manages remote proxy services."""

    def __init__(self, hass, entry, remote):
        """Initialize a new ProxyServices instance."""
        self.hass = hass
        self.entry = entry
        self.remote = remote
        self.remote_services = {}
        self.registered_services = []

    @property
    def services(self):
        """Return list of service names."""
        result = []
        for domain, services in self.remote_services.items():
            for service in services.keys():
                result.append(f"{domain}.{service}")
        return sorted(result)

    async def load(self):
        """Call to make initial registration of services."""
        await self.remote.call(self._async_got_services, "get_services")

    async def unload(self):
        """Call to unregister all registered services."""
        description_cache = self.hass.data[SERVICE_DESCRIPTION_CACHE]

        for domain, service_name in self.registered_services:
            self.hass.services.async_remove(domain, service_name)

            # Remove from internal description cache
            service = f"{domain}.{service_name}"
            if service in description_cache:
                del description_cache[service]

    async def _async_got_services(self, message):
        """Called when list of remote services is available."""
        self.remote_services = message["result"]

        # A service prefix is needed to not clash with original service names
        service_prefix = self.entry.options.get(CONF_SERVICE_PREFIX)
        if not service_prefix:
            return

        description_cache = self.hass.data[SERVICE_DESCRIPTION_CACHE]
        for service in self.entry.options.get(CONF_SERVICES, []):
            domain, service_name = service.split(".")
            service = service_prefix + service_name

            # Register new service with same name as original service but with prefix
            self.hass.services.async_register(
                domain,
                service,
                self._async_handle_service_call,
                vol.Schema({}, extra=vol.ALLOW_EXTRA),
            )

            # <HERE_BE_DRAGON>
            # Service metadata can only be provided via a services.yaml file for a
            # particular component, something not possible here. A cache is used
            # internally for loaded service descriptions and that's abused here. If
            # the internal representation of the cache change, this sill break.
            # </HERE_BE_DRAGONS>
            service_info = self.remote_services.get(domain, {}).get(service_name)
            if service_info:
                description_cache[f"{domain}.{service}"] = service_info

            self.registered_services.append((domain, service))

    async def _async_handle_service_call(self, event):
        """Handle service call to proxy service."""
        # An eception must be raised from the service call handler (thus method) in
        # order to end up in the frontend. The code below synchronizes reception of
        # the service call result, so potential error message can be used as exception
        # message. Not very pretty...
        ev = asyncio.Event()
        res = None

        def _resp(message):
            nonlocal res
            res = message
            ev.set()

        service_prefix = self.entry.options.get(CONF_SERVICE_PREFIX)
        service = event.service[len(service_prefix) :]
        await self.remote.call(
            _resp,
            "call_service",
            domain=event.domain,
            service=service,
            service_data=event.data.copy(),
        )

        await asyncio.wait_for(ev.wait(), SERVICE_CALL_LIMIT)
        if not res["success"]:
            raise HomeAssistantError(res["error"]["message"])
