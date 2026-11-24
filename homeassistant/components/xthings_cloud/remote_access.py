"""Remote access management via FRP."""

import asyncio
import configparser
import json
import platform
import stat
from pathlib import Path
from typing import Any

import aiohttp
import yaml
from ha_xthings_cloud import XthingsCloudApiClient
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, FRP_S3_BASE_URL, LOGGER

FRPC_CONFIG_FILENAME = "frpc.toml"
FRP_UPGRADE_INI_URL = f"{FRP_S3_BASE_URL}/upgrade.ini"
FRP_VERSION_FILENAME = "version.txt"

PLATFORM_MAP: dict[tuple[str, str], str] = {
    ("Darwin", "arm64"): "darwin_arm64",
    ("Darwin", "x86_64"): "darwin_amd64",
    ("Linux", "aarch64"): "linux_arm64",
    ("Linux", "x86_64"): "linux_amd64",
    ("Linux", "armv7l"): "linux_arm64",
}


def _get_frp_dir() -> Path:
    """Return the FRP directory inside the component."""
    return Path(__file__).parent / "frp"


def _get_platform_key() -> str | None:
    """Get the download key for the current platform."""
    key = PLATFORM_MAP.get((platform.system(), platform.machine()))
    if not key:
        LOGGER.error("Unsupported platform: %s %s", platform.system(), platform.machine())
    return key


def _get_local_version(frp_dir: Path) -> str | None:
    """Read the locally stored frpc version."""
    version_file = frp_dir / FRP_VERSION_FILENAME
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return None


def _save_local_version(frp_dir: Path, version: str) -> None:
    """Save the frpc version locally."""
    (frp_dir / FRP_VERSION_FILENAME).write_text(version, encoding="utf-8")


async def _async_fetch_upgrade_info(
    session: aiohttp.ClientSession,
) -> dict[str, str] | None:
    """Fetch and parse the FRP upgrade manifest."""
    try:
        async with session.get(FRP_UPGRADE_INI_URL) as response:
            response.raise_for_status()
            text = await response.text()
    except aiohttp.ClientError as err:
        LOGGER.error("Failed to fetch frpc upgrade info: %s", err)
        return None

    parser = configparser.ConfigParser()
    parser.read_string("[frp]\n" + text)
    return {
        key: value.strip('"').strip("'")
        for key, value in parser.items("frp")
    }


async def _async_download_frpc(
    session: aiohttp.ClientSession,
    download_path: str,
    destination: Path,
) -> bool:
    """Download a platform-specific frpc binary."""
    try:
        async with session.get(f"{FRP_S3_BASE_URL}/{download_path}") as response:
            response.raise_for_status()
            content = await response.read()
    except aiohttp.ClientError as err:
        LOGGER.error("Failed to download frpc: %s", err)
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    destination.chmod(
        destination.stat().st_mode
        | stat.S_IXUSR
        | stat.S_IXGRP
        | stat.S_IXOTH
    )
    LOGGER.info("Downloaded frpc to %s (%d bytes)", destination, len(content))
    return True


async def async_ensure_frpc(hass: HomeAssistant) -> Path | None:
    """Ensure the local frpc binary exists and is current."""
    platform_key = _get_platform_key()
    if not platform_key:
        return None

    frp_dir = _get_frp_dir()
    frpc_path = frp_dir / platform_key / "frpc"
    await hass.async_add_executor_job(frp_dir.mkdir, 0o755, True, True)

    info = await _async_fetch_upgrade_info(async_get_clientsession(hass))
    if not info:
        if frpc_path.exists():
            LOGGER.warning("Cannot check frpc update; using existing binary")
            return frpc_path
        LOGGER.error("Cannot download frpc: upgrade info unavailable")
        return None

    remote_version = info.get("version", "")
    remote_path = info.get(platform_key)
    if not remote_path:
        LOGGER.error("No download path for platform %s", platform_key)
        return frpc_path if frpc_path.exists() else None

    local_version = await hass.async_add_executor_job(_get_local_version, frp_dir)
    needs_download = not frpc_path.exists() or local_version != remote_version
    if needs_download:
        if not await _async_download_frpc(async_get_clientsession(hass), remote_path, frpc_path):
            return frpc_path if frpc_path.exists() else None
        await hass.async_add_executor_job(_save_local_version, frp_dir, remote_version)

    return frpc_path


def _get_frpc_config_path(hass: HomeAssistant) -> Path:
    """Return the FRP config path in the HA config directory."""
    return Path(hass.config.config_dir) / FRPC_CONFIG_FILENAME


def _build_frpc_toml(
    data: dict[str, Any], ha_port: int = 8123, client_id: str = ""
) -> str:
    """Build the FRP TOML configuration from the cloud API response."""
    http_config = data.get("http", {})
    lines = [
        f'clientID = "{client_id}"',
        f'serverAddr = "{data.get("serverAddr", "")}"',
        f"serverPort = {data.get('serverPort', 7002)}",
        "loginFailExit = false",
        'auth.method = "token"',
        f'auth.token = "{data.get("auth_token", "")}"',
        f'metadatas.jwt = "{data.get("metadatas_jwt", "")}"',
        "",
        "[transport]",
        f'protocol = "{data.get("transport_protocol", "kcp")}"',
        "",
        "[[proxies]]",
        f'name = "{http_config.get("name", "")}"',
        f'type = "{http_config.get("type", "http")}"',
        'localIP = "127.0.0.1"',
        f"localPort = {ha_port}",
        f'subdomain = "{http_config.get("subdomain", "")}"',
    ]
    request_headers = http_config.get("requestHeaders", {})
    if isinstance(request_headers, dict):
        header_values = request_headers.get("set", {})
        if isinstance(header_values, dict):
            for header_name, header_value in header_values.items():
                lines.append(
                    f"requestHeaders.set.{header_name} = {json.dumps(str(header_value))}"
                )
    return "\n".join(lines) + "\n"


def _get_ha_port(hass: HomeAssistant) -> int:
    """Get the configured Home Assistant HTTP port."""
    http_config = hass.data.get("http")
    if http_config and hasattr(http_config, "server_port"):
        return http_config.server_port
    return 8123


def _ensure_executable(path: Path) -> None:
    """Ensure the FRP binary is executable."""
    mode = path.stat().st_mode
    if not mode & stat.S_IXUSR:
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


async def _async_verify_frpc_config(frpc_path: Path, config_path: Path) -> bool:
    """Validate the generated FRPC configuration before starting it."""
    try:
        process = await asyncio.create_subprocess_exec(
            str(frpc_path),
            "verify",
            "-c",
            str(config_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
    except OSError as err:
        LOGGER.error("Failed to verify frpc config: %s", err)
        return False
    if process.returncode:
        details = output.decode(errors="replace").strip()
        LOGGER.error("Invalid frpc config (exit %s): %s", process.returncode, details)
        return False
    return True


async def _async_start_frpc(
    hass: HomeAssistant, frpc_path: Path
) -> asyncio.subprocess.Process | None:
    """Start frpc with the generated configuration."""
    config_path = _get_frpc_config_path(hass)
    if not config_path.exists():
        LOGGER.error("Frpc config not found: %s", config_path)
        return None

    await hass.async_add_executor_job(_ensure_executable, frpc_path)
    if not await _async_verify_frpc_config(frpc_path, config_path):
        return None
    try:
        process = await asyncio.create_subprocess_exec(
            str(frpc_path),
            "-c",
            str(config_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as err:
        LOGGER.error("Failed to start frpc: %s", err)
        return None

    LOGGER.info("Frpc started (pid=%s)", process.pid)
    hass.async_create_task(_async_log_frpc_output(process))
    return process


async def _async_log_frpc_output(process: asyncio.subprocess.Process) -> None:
    """Log frpc output and report unexpected process exits."""
    if process.stdout is None:
        return
    try:
        while line := await process.stdout.readline():
            LOGGER.debug("frpc: %s", line.decode(errors="replace").rstrip())
        returncode = await process.wait()
    except (OSError, asyncio.CancelledError):
        return
    if returncode:
        LOGGER.error("Frpc exited unexpectedly with code %s", returncode)
    else:
        LOGGER.info("Frpc exited")


async def _async_stop_frpc(hass: HomeAssistant) -> None:
    """Stop the running frpc process."""
    process: asyncio.subprocess.Process | None = hass.data.get(f"{DOMAIN}_frpc_process")
    if process and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()
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
            yaml.safe_dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


async def async_enable_remote_access(
    hass: HomeAssistant, client: XthingsCloudApiClient, client_id: str
) -> str | None:
    """Fetch cloud FRP settings, write config, and start frpc."""
    await _async_stop_frpc(hass)
    frpc_path = await async_ensure_frpc(hass)
    if not frpc_path:
        return None

    try:
        data = await client.async_get_frp_config(client_id)
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Failed to get FRP config: %s", err)
        return None

    config_path = _get_frpc_config_path(hass)
    config_path.write_text(
        _build_frpc_toml(data, _get_ha_port(hass), client_id),
        encoding="utf-8",
    )
    await hass.async_add_executor_job(_ensure_http_proxy_config, hass)

    process = await _async_start_frpc(hass, frpc_path)
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
    if await hass.async_add_executor_job(config_path.exists):
        await hass.async_add_executor_job(config_path.unlink)
