"""Remote access management via FRP."""

from __future__ import annotations

import asyncio
import configparser
import platform
import stat
from pathlib import Path
from typing import Any

import aiohttp
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import XthingsCloudApiClient
from .const import DOMAIN, FRP_S3_BASE_URL, LOGGER

FRPC_CONFIG_FILENAME = "frpc.toml"

# S3 upgrade manifest URL
FRP_UPGRADE_INI_URL = f"{FRP_S3_BASE_URL}/upgrade.ini"

# Platform to INI key mapping
# Format: {(system, machine): ini_key}
PLATFORM_MAP: dict[tuple[str, str], str] = {
    ("Darwin", "arm64"): "darwin_arm64",
    ("Darwin", "x86_64"): "darwin_amd64",
    ("Linux", "aarch64"): "linux_arm64",
    ("Linux", "x86_64"): "linux_amd64",
    ("Linux", "armv7l"): "linux_arm64",  # ARM 32-bit fallback
}

# Local version tracking file
FRP_VERSION_FILENAME = "version.txt"


def _get_frp_dir() -> Path:
    """Return the frp directory inside the component."""
    return Path(__file__).parent / "frp"


def _get_platform_key() -> str | None:
    """Get the INI key for current platform."""
    system = platform.system()
    machine = platform.machine()
    key = PLATFORM_MAP.get((system, machine))
    if not key:
        LOGGER.error(
            "Unsupported platform: %s %s. Supported: %s",
            system, machine, list(PLATFORM_MAP.keys()),
        )
    return key


def _get_local_version(frp_dir: Path) -> str | None:
    """Read locally stored frpc version."""
    version_file = frp_dir / FRP_VERSION_FILENAME
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return None


def _save_local_version(frp_dir: Path, version: str) -> None:
    """Save frpc version to local file."""
    version_file = frp_dir / FRP_VERSION_FILENAME
    version_file.write_text(version, encoding="utf-8")


async def _async_fetch_upgrade_info(
    session: aiohttp.ClientSession,
) -> dict[str, str] | None:
    """Fetch and parse uprade.ini from S3. Returns dict of key-value pairs."""
    try:
        async with session.get(FRP_UPGRADE_INI_URL) as resp:
            resp.raise_for_status()
            text = await resp.text()
    except aiohttp.ClientError as err:
        LOGGER.error("Failed to fetch frpc upgrade info: %s", err)
        return None

    # Parse INI-style content (key = "value" format, no section headers)
    # Add a default section header for configparser
    ini_text = "[frp]\n" + text
    parser = configparser.ConfigParser()
    parser.read_string(ini_text)

    result: dict[str, str] = {}
    for key, value in parser.items("frp"):
        # Strip surrounding quotes
        result[key] = value.strip('"').strip("'")
    return result


async def _async_download_frpc(
    session: aiohttp.ClientSession,
    download_path: str,
    dest_path: Path,
) -> bool:
    """Download frpc binary from S3."""
    url = f"{FRP_S3_BASE_URL}/{download_path}"
    LOGGER.info("Downloading frpc from %s", url)
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            content = await resp.read()
            dest_path.write_bytes(content)
            # Set executable permission
            dest_path.chmod(
                dest_path.stat().st_mode
                | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
        LOGGER.info("frpc downloaded to %s (%d bytes)", dest_path, len(content))
        return True
    except aiohttp.ClientError as err:
        LOGGER.error("Failed to download frpc: %s", err)
        return False


async def async_ensure_frpc(hass: HomeAssistant) -> Path | None:
    """Ensure frpc binary exists and is up-to-date. Returns binary path or None."""
    platform_key = _get_platform_key()
    if not platform_key:
        return None

    frp_dir = _get_frp_dir()
    frpc_path = frp_dir / platform_key / "frpc"

    # Ensure frp directory exists
    await hass.async_add_executor_job(frp_dir.mkdir, 0o755, True, True)

    session = async_get_clientsession(hass)

    # Fetch remote version info
    info = await _async_fetch_upgrade_info(session)
    if not info:
        # If fetch fails but local binary exists, use it
        if frpc_path.exists():
            LOGGER.warning("Cannot check frpc update, using existing binary")
            return frpc_path
        LOGGER.error("Cannot download frpc: upgrade info unavailable")
        return None

    remote_version = info.get("version", "")
    remote_path = info.get(platform_key)
    if not remote_path:
        LOGGER.error("No download path for platform %s in upgrade info", platform_key)
        if frpc_path.exists():
            return frpc_path
        return None

    # Compare versions
    local_version = await hass.async_add_executor_job(_get_local_version, frp_dir)

    needs_download = False
    if not frpc_path.exists():
        LOGGER.info("frpc binary not found, downloading v%s", remote_version)
        needs_download = True
    elif local_version != remote_version:
        LOGGER.info(
            "frpc update available: %s -> %s",
            local_version or "unknown", remote_version,
        )
        needs_download = True

    if needs_download:
        success = await _async_download_frpc(session, remote_path, frpc_path)
        if not success:
            if frpc_path.exists():
                LOGGER.warning("Download failed, using existing frpc binary")
                return frpc_path
            return None
        await hass.async_add_executor_job(_save_local_version, frp_dir, remote_version)

    return frpc_path


def _get_frpc_config_path(hass: HomeAssistant) -> Path:
    """Return the frpc.toml path in HA config directory."""
    return Path(hass.config.config_dir) / FRPC_CONFIG_FILENAME


def _build_frpc_toml(data: dict[str, Any], ha_port: int = 8123, client_id: str = "") -> str:
    """Build frpc.toml content from API response data."""
    server_addr = data.get("serverAddr", "")
    server_port = data.get("serverPort", 7002)
    auth_token = data.get("auth_token", "")
    metadatas_jwt = data.get("metadatas_jwt", "")
    transport_protocol = data.get("transport_protocol", "kcp")

    http_config = data.get("http", {})
    proxy_name = http_config.get("name", "")
    proxy_type = http_config.get("type", "http")
    subdomain = http_config.get("subdomain", "")

    lines = [
        f'clientID = "{client_id}"',
        f'serverAddr = "{server_addr}"',
        f"serverPort = {server_port}",
        f"loginFailExit = false",
        f'auth.method = "token"',
        f'auth.token = "{auth_token}"',
        f'metadatas.jwt = "{metadatas_jwt}"',
        "",
        "[transport]",
        f'protocol = "{transport_protocol}"',
        "",
        "[[proxies]]",
        f'name = "{proxy_name}"',
        f'type = "{proxy_type}"',
        f"localPort = {ha_port}",
        f'subdomain = "{subdomain}"',
    ]
    return "\n".join(lines) + "\n"


def _get_ha_port(hass: HomeAssistant) -> int:
    """Get current HA web server port from http component config."""
    http_config = hass.data.get("http")
    if http_config and hasattr(http_config, "server_port"):
        return http_config.server_port
    return 8123


def _ensure_executable(path: Path) -> None:
    """Ensure the binary has execute permission."""
    current = path.stat().st_mode
    if not current & stat.S_IXUSR:
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


async def _async_start_frpc(
    hass: HomeAssistant, frpc_path: Path,
) -> asyncio.subprocess.Process | None:
    """Start frpc process."""
    config_path = _get_frpc_config_path(hass)
    if not config_path.exists():
        LOGGER.error("frpc config not found: %s", config_path)
        return None

    await hass.async_add_executor_job(_ensure_executable, frpc_path)

    LOGGER.info("Starting frpc: %s -c %s", frpc_path, config_path)
    try:
        process = await asyncio.create_subprocess_exec(
            str(frpc_path), "-c", str(config_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        LOGGER.info("frpc started (pid=%s)", process.pid)
        asyncio.create_task(_async_log_frpc_output(process))
        return process
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Failed to start frpc: %s", err)
        return None


async def _async_log_frpc_output(process: asyncio.subprocess.Process) -> None:
    """Log frpc stdout/stderr in background."""
    try:
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            LOGGER.debug("frpc: %s", line.decode().rstrip())
    except Exception:  # noqa: BLE001
        pass


async def _async_stop_frpc(hass: HomeAssistant) -> None:
    """Stop frpc process if running."""
    process: asyncio.subprocess.Process | None = hass.data.get(f"{DOMAIN}_frpc_process")
    if process and process.returncode is None:
        LOGGER.info("Stopping frpc (pid=%s)", process.pid)
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        LOGGER.info("frpc stopped")
    hass.data.pop(f"{DOMAIN}_frpc_process", None)


def _ensure_http_proxy_config(hass: HomeAssistant) -> None:
    """Ensure configuration.yaml has http reverse proxy settings for FRP."""
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
    needs_update = False

    if not isinstance(http_config, dict):
        http_config = {}
        needs_update = True

    if not http_config.get("use_x_forwarded_for"):
        http_config["use_x_forwarded_for"] = True
        needs_update = True

    trusted = http_config.get("trusted_proxies")
    if not isinstance(trusted, list) or "127.0.0.1" not in trusted:
        if not isinstance(trusted, list):
            trusted = []
        trusted.append("127.0.0.1")
        http_config["trusted_proxies"] = trusted
        needs_update = True

    if not needs_update:
        return

    config["http"] = http_config

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
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                config, f, default_flow_style=False,
                allow_unicode=True, sort_keys=False,
            )

    LOGGER.info("Updated configuration.yaml with HTTP reverse proxy settings")


async def async_enable_remote_access(
    hass: HomeAssistant, client: XthingsCloudApiClient, client_id: str
) -> str | None:
    """Enable remote access: auto-update frpc, fetch FRP config, write frpc.toml, start frpc."""
    # Stop existing frpc if running
    await _async_stop_frpc(hass)

    # Ensure frpc binary is available and up-to-date
    frpc_path = await async_ensure_frpc(hass)
    if not frpc_path:
        LOGGER.error("Cannot enable remote access: frpc binary unavailable")
        return None

    try:
        data = await client.async_get_frp_config(client_id)
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Failed to get FRP config: %s", err)
        return None

    ha_port = _get_ha_port(hass)
    toml_content = _build_frpc_toml(data, ha_port, client_id)
    config_path = _get_frpc_config_path(hass)

    await hass.async_add_executor_job(config_path.write_text, toml_content)
    LOGGER.info("FRP config written to %s", config_path)

    # Ensure HA http is configured for reverse proxy
    await hass.async_add_executor_job(_ensure_http_proxy_config, hass)

    # Start frpc process
    process = await _async_start_frpc(hass, frpc_path)
    if process:
        hass.data[f"{DOMAIN}_frpc_process"] = process

    subdomain = data.get("http", {}).get("subdomain", "")
    if subdomain:
        LOGGER.info("Remote access enabled: https://%s.gw.xthings.com", subdomain)
    return subdomain


async def async_disable_remote_access(hass: HomeAssistant) -> None:
    """Disable remote access: stop frpc and remove frpc.toml."""
    await _async_stop_frpc(hass)

    config_path = _get_frpc_config_path(hass)
    if await hass.async_add_executor_job(config_path.exists):
        await hass.async_add_executor_job(config_path.unlink)
        LOGGER.info("FRP config removed: %s", config_path)
