"""Config flow for Velux integration."""

from typing import Any

from pyvlx import PyVLX, PyVLXException
from pyvlx.discovery import VeluxDiscovery, VeluxHost
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class VeluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for velux."""

    VERSION = 1
    MINOR_VERSION = 2

    hosts: list[VeluxHost] = []

    async def async_step_import(self, config: dict[str, Any]) -> ConfigFlowResult:
        """Import a config entry."""

        def create_repair(error: str | None = None) -> None:
            if error:
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_yaml_import_issue_{error}",
                    breaks_in_ha_version="2024.9.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key=f"deprecated_yaml_import_issue_{error}",
                )
            else:
                async_create_issue(
                    self.hass,
                    HOMEASSISTANT_DOMAIN,
                    f"deprecated_yaml_{DOMAIN}",
                    breaks_in_ha_version="2024.9.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_yaml",
                    translation_placeholders={
                        "domain": DOMAIN,
                        "integration_title": "Velux",
                    },
                )

        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == config[CONF_HOST]:
                create_repair()
                return self.async_abort(reason="already_configured")

        pyvlx = PyVLX(host=config[CONF_HOST], password=config[CONF_PASSWORD])
        try:
            await pyvlx.connect()
            await pyvlx.disconnect()
        except (PyVLXException, ConnectionError):
            create_repair("cannot_connect")
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            create_repair("unknown")
            return self.async_abort(reason="unknown")

        create_repair()
        return self.async_create_entry(
            title=config[CONF_HOST],
            data=config,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if self.hosts:
                for host in self.hosts:
                    if user_input[CONF_HOST] == host.ip_address:
                        await self.async_set_unique_id(host.hostname)
                        self._abort_if_unique_id_configured(
                            updates={CONF_HOST: host.ip_address}
                        )

            pyvlx = PyVLX(
                host=user_input[CONF_HOST], password=user_input[CONF_PASSWORD]
            )
            try:
                await pyvlx.connect()
                await pyvlx.disconnect()
            except (PyVLXException, ConnectionError) as err:
                errors["base"] = "cannot_connect"
                LOGGER.debug("Cannot connect: %s", err)
            except Exception as err:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        if not self.hosts:
            aiozc = await zeroconf.async_get_async_instance(self.hass)
            vd: VeluxDiscovery = VeluxDiscovery(zeroconf=aiozc)
            if await vd.async_discover_hosts(expected_hosts=1):
                self.hosts = vd.hosts  # type: ignore[assignment]

        if self.hosts:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_HOST): SelectSelector(
                        SelectSelectorConfig(
                            options=[host.ip_address for host in self.hosts],
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )
        else:
            data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_unignore(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Rediscover a previously ignored discover."""
        unique_id = user_input["unique_id"]
        await self.async_set_unique_id(unique_id)
        return await self.async_step_user()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery by zeroconf."""
        hostname = discovery_info.hostname.replace(".local.", "")
        await self.async_set_unique_id(hostname)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        # Check if config_entry exists already without unigue_id configured.
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_HOST] == discovery_info.host and entry.unique_id is None:
                self.hass.config_entries.async_update_entry(
                    entry=entry, unique_id=hostname
                )
                return self.async_abort(reason="already_configured")

        self.hosts.append(VeluxHost(hostname=hostname, ip_address=discovery_info.host))
        return await self.async_step_user()
