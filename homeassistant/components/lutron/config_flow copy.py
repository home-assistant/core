import aiohttp
import ipaddress
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_IP_ADDRESS, DOMAIN

from .const import DOMAIN

class LutronConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Validate user input
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)
            ip_address = user_input.get(CONF_IP_ADDRESS)

            # Perform any validation here
            if not username or not password or not ip_address:
                errors["base"] = "missing_fields"
            else:
                # Check if a configuration entry with the same unique ID already exists
                existing_entries = self.hass.config_entries.async_entries(DOMAIN)
                for entry in existing_entries:
                    if entry.data[CONF_IP_ADDRESS] == ip_address:
                        errors["base"] = "already_configured"

            if not errors:
                await self.async_set_unique_id(ip_address.replace(".", "_"))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Lutron Integration", data=user_input
                )

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_IP_ADDRESS): str,
            }),
            errors=errors,
        )
    
    async def async_discover(self):
        """Discover devices on the local network."""
        discovered_devices = []

        # Get the subnet mask from the Home Assistant instance
        subnet_mask = self.hass.data['subnet_mask']  # Replace with the actual way to retrieve the subnet mask

        # Get the subnet of the Home Assistant host using the subnet mask
        host_ip = self.hass.data['host_ip']  # Replace with the actual way to retrieve the host IP
        subnet = ipaddress.IPv4Network(f"{host_ip}/{subnet_mask}", strict=False)

        tasks = []
        for ip in subnet.hosts():
            tasks.append(self._check_ip(ip))

        results = await asyncio.gather(*tasks)
        for ip, has_content in results:
            if has_content:
                discovered_devices.append({"host": str(ip)})

        return discovered_devices

    async def _check_ip(self, ip):
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{ip}/your-web-page"
                async with session.get(url) as response:
                    page_content = await response.text()
                    has_content = "desired_content" in page_content  # Check for the desired content
        except Exception:
            has_content = False

        return ip, has_content
