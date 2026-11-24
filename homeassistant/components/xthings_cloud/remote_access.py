"""Remote access management via FRP."""

import asyncio
from pathlib import Path

from ha_xthings_cloud import (
    XthingsCloudApiClient,
    async_start_frpc,
    async_stop_frpc,
    remove_frpc_config,
)
import yaml

from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER

FRPC_CONFIG_FILENAME = "frpc.toml"


def _get_frp_dir() -> Path:
    """Return the FRP directory inside the component."""
    return Path(__file__).parent / "frp"


def _get_frpc_config_path(hass: HomeAssistant) -> Path:
    """Return the FRP config path in the HA config directory."""
    return Path(hass.config.config_dir) / FRPC_CONFIG_FILENAME


def _get_ha_port(hass: HomeAssistant) -> int:
    """Get the configured Home Assistant HTTP port."""
    http_config = hass.data.get("http")
    if http_config and hasattr(http_config, "server_port"):
        return http_config.server_port
    return 8123


async def _async_stop_frpc(hass: HomeAssistant) -> None:
    """Stop the running FRPC process."""
    process: asyncio.subprocess.Process | None = hass.data.get(f"{DOMAIN}_frpc_process")
    await async_stop_frpc(process)
    hass.data.pop(f"{DOMAIN}_frpc_process", None)


def _ensure_http_proxy_config(hass: HomeAssistant) -> None:
    """Ensure HA trusts the local FRP reverse proxy."""
    config_path = Path(hass.config.config_dir) / "configuration.yaml"
    if not config_path.exists():
        return

    content = config_path.read_text(encoding="utf-8")
    try:
        config = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        LOGGER.error("Failed to parse configuration.yaml")
        return

    http_config = config.get("http")
    if not isinstance(http_config, dict):
        http_config = {}
    http_config["use_x_forwarded_for"] = True
    trusted = http_config.get("trusted_proxies")
    if not isinstance(trusted, list):
        trusted = []
    if "127.0.0.1" not in trusted:
        trusted.append("127.0.0.1")
    http_config["trusted_proxies"] = trusted

    if "http:" not in content:
        block = (
            "\n# Auto-configured by Xthings Cloud for remote access\n"
            "http:\n"
            "  use_x_forwarded_for: true\n"
            "  trusted_proxies:\n"
            "    - 127.0.0.1\n"
        )
        config_path.write_text(content.rstrip() + "\n" + block, encoding="utf-8")
    else:
        config["http"] = http_config
        config_path.write_text(
            yaml.safe_dump(
                config, default_flow_style=False, allow_unicode=True, sort_keys=False
            ),
            encoding="utf-8",
        )


async def async_enable_remote_access(
    hass: HomeAssistant, client: XthingsCloudApiClient, client_id: str
) -> str | None:
    """Fetch cloud FRP settings, write config, and start frpc."""
    await _async_stop_frpc(hass)
    frpc_path_text = await client.async_ensure_frpc(str(_get_frp_dir()))
    frpc_path = Path(frpc_path_text) if frpc_path_text else None
    if not frpc_path:
        return None

    config_path = _get_frpc_config_path(hass)
    try:
        data = await client.async_create_frpc_config(
            client_id, str(config_path), _get_ha_port(hass)
        )
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Failed to get or write FRP config: %s", err)
        return None

    await hass.async_add_executor_job(_ensure_http_proxy_config, hass)

    process = await async_start_frpc(frpc_path, config_path)
    if process:
        hass.data[f"{DOMAIN}_frpc_process"] = process

    subdomain = data.get("http", {}).get("subdomain", "")
    if subdomain:
        LOGGER.info("Remote access enabled: https://%s.gw.xthings.com", subdomain)
    return subdomain


async def async_disable_remote_access(hass: HomeAssistant) -> None:
    """Stop frpc and remove its generated configuration."""
    await _async_stop_frpc(hass)
    config_path = _get_frpc_config_path(hass)
    await hass.async_add_executor_job(remove_frpc_config, config_path)
