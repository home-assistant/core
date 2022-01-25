"""The command_line component."""
from __future__ import annotations

import logging
import subprocess

from homeassistant import config as conf_util
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the command_line integration."""
    if DOMAIN in config:
        await _process_config(hass, config)

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload top-level + platforms."""
        try:
            unprocessed_conf = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        conf = await conf_util.async_process_component_config(
            hass, unprocessed_conf, await async_get_integration(hass, DOMAIN)
        )

        if conf is None:
            return

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

        if DOMAIN in conf:
            await _process_config(hass, conf)

        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_RELOAD, _reload_config
    )

    return True


async def _process_config(hass: HomeAssistant, hass_config: ConfigType) -> None:
    """Process config."""
    for conf_section in hass_config[DOMAIN]:
        for platform_domain in PLATFORMS:
            if platform_domain in conf_section:
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass,
                        platform_domain,
                        DOMAIN,
                        {
                            "entities": conf_section[platform_domain],
                        },
                        hass_config,
                    )
                )


def call_shell_with_timeout(command, timeout, *, log_return_code=True):
    """Run a shell command with a timeout.

    If log_return_code is set to False, it will not print an error if a non-zero
    return code is returned.
    """
    try:
        _LOGGER.debug("Running command: %s", command)
        subprocess.check_output(
            command, shell=True, timeout=timeout  # nosec # shell by design
        )
        return 0
    except subprocess.CalledProcessError as proc_exception:
        if log_return_code:
            _LOGGER.error("Command failed: %s", command)
        return proc_exception.returncode
    except subprocess.TimeoutExpired:
        _LOGGER.error("Timeout for command: %s", command)
        return -1
    except subprocess.SubprocessError:
        _LOGGER.error("Error trying to exec command: %s", command)
        return -1


def check_output_or_log(command, timeout):
    """Run a shell command with a timeout and return the output."""
    try:
        return_value = subprocess.check_output(
            command, shell=True, timeout=timeout  # nosec # shell by design
        )
        return return_value.strip().decode("utf-8")
    except subprocess.CalledProcessError:
        _LOGGER.error("Command failed: %s", command)
    except subprocess.TimeoutExpired:
        _LOGGER.error("Timeout for command: %s", command)
    except subprocess.SubprocessError:
        _LOGGER.error("Error trying to exec command: %s", command)

    return None
