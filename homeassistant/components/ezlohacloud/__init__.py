import asyncio
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
from typing import Optional

import aiohttp
import requests
import tomli
import tomli_w

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from .config_flow import ExampleConfigFlow
from .const import DOMAIN, EZLO_API_URI
from .frp_helpers import fetch_and_update_frp_config, start_frpc

_LOGGER = logging.getLogger(__name__)

# Architecture mapping
ARCH_MAP = {
    "aarch64": "arm64",
    "x86_64": "amd64",
    "amd64": "amd64",
    "armv7l": "arm",
    "armhf": "arm",
    "i386": "386",
    "i686": "386",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up frpc client from a config entry."""
    config = entry.data

    try:
        # Install/update frpc binary
        version = "0.61.0"  # config["frp_version"]
        machine = await get_system_architecture(hass)
        binary_path = await install_frpc(hass, version, machine)

        # Proceed with configuration setup
        return await setup_frpc_configuration(hass, entry, config, binary_path)

    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to setup FRPC: {err}") from err


async def install_frpc(hass: HomeAssistant, version: str, machine: str) -> str:
    """Install FRPC binary for specific version and architecture."""
    integration_dir = Path(__file__).parent
    bin_dir = integration_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    binary_path = bin_dir / "frpc"

    # Check if we need to update the binary
    if await check_binary_current(binary_path, version):
        _LOGGER.debug("Using existing FRPC binary v%s", version)
        return str(binary_path)

    _LOGGER.info("Installing FRPC v%s for %s architecture", version, machine)
    return await hass.async_add_executor_job(
        _sync_install_frpc, version, machine, binary_path
    )


def _sync_install_frpc(version: str, machine: str, binary_path: Path) -> str:
    """Executor for FRPC installation."""
    url = f"https://github.com/fatedier/frp/releases/download/v{version}/frp_{version}_linux_{machine}.tar.gz"

    with tempfile.TemporaryDirectory() as temp_dir:
        tar_path = Path(temp_dir) / "frpc.tar.gz"

        # Download frp release
        try:
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(tar_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
        except requests.RequestException as err:
            raise Exception(f"Download failed: {err}") from err  # noqa: TRY002

        # Extract binary
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                members = [m for m in tar.getmembers() if m.name.endswith("/frpc")]
                if not members:
                    raise Exception("No frpc binary found in release package")
                tar.extract(members[0], path=temp_dir)
        except tarfile.TarError as err:
            raise Exception(f"Extraction failed: {err}") from err

        # Install binary
        extracted_bin = Path(temp_dir) / members[0].name
        shutil.copy(extracted_bin, binary_path)
        binary_path.chmod(0o755)

    _LOGGER.info("Successfully installed FRPC to %s", binary_path)
    return str(binary_path)


async def check_binary_current(binary_path: Path, version: str) -> bool:
    """Check if existing binary matches required version."""
    if not binary_path.exists():
        return False

    try:
        # Create async subprocess
        proc = await asyncio.create_subprocess_exec(
            str(binary_path),
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for process to complete with timeout
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return False

        # Check version in output
        output = stdout.decode().strip()
        return version in output

    except Exception as err:
        _LOGGER.debug("Version check error: %s", err)
        return False


async def get_system_architecture(hass: HomeAssistant) -> str:
    """Determine system architecture with Home Assistant compatibility."""
    arch = platform.machine().lower()
    return ARCH_MAP.get(arch, "amd64")


async def setup_frpc_configuration(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Add entry parameter here
    config: dict,
    binary_path: str,
) -> bool:
    """Configure and start FRPC client."""

    auth_data = get_config_data(hass)
    token = auth_data["auth_token"]
    uuid = auth_data["user"]["uuid"]
    is_logged_in = auth_data["is_logged_in"]

    if not is_logged_in and not token:
        return False

    config_path = Path(__file__).parent / "config" / "frpc.toml"

    try:
        _LOGGER.debug("FRPC configuration generated at %s", config_path)

        try:
            await fetch_and_update_frp_config(hass=hass, uuid=uuid, token=token)

            await start_frpc(hass=hass, config_entry=entry)
        except Exception as err:
            _LOGGER.error("Failed to fetch the server details: %s", err)
            raise err
    except Exception as err:
        _LOGGER.error("Configuration failed: %s", err)
        return False

    return True


def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Get the first config entry for this integration."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ValueError("No config entry found")
    return entries[0]


def get_config_data(hass: HomeAssistant) -> dict:
    """Get the configuration data dictionary."""
    entry = get_config_entry(hass)
    return entry.data


async def generate_config_file(
    hass: HomeAssistant, config: dict, config_path: str
) -> None:
    """Generate FRPC configuration file."""
    default_config = Path(__file__).parent / "config" / "frpc.toml"

    auth_data = get_config_data(hass)
    token = auth_data["auth_token"]
    is_logged_in = auth_data["is_logged_in"]

    if not is_logged_in and not token:
        return

    try:
        # Fetch configuration from API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{EZLO_API_URI}/api/user/{token}/server-config", timeout=10
            ) as response:
                response.raise_for_status()
                api_config = await response.json()

        # Extract server configuration from nested structure
        server_config = api_config["serverConfig"]

        # Build TOML structure matching YAML format
        config_data = {
            "serverAddr": server_config["serverAddr"],
            "serverPort": server_config["serverPort"],
            "proxies": [],
        }

        # Add proxies with array-of-tables syntax
        for proxy in server_config["proxies"]:
            config_data["proxies"].append(
                {
                    "name": proxy["name"],
                    "type": proxy["type"],
                    "localPort": proxy["localPort"],
                    "subdomain": proxy["subdomain"],
                }
            )

        # Write TOML file using async executor
        def _sync_write():
            with open(config_path, "wb") as f:
                tomli_w.dump(config_data, f)

        await hass.async_add_executor_job(_sync_write)

    except KeyError as err:
        _LOGGER.error("Missing expected key in API response: %s", err)
        raise
    except aiohttp.ClientError as err:
        _LOGGER.error("API request failed: %s", err)
        raise
    except Exception as err:
        _LOGGER.error("Configuration generation failed: %s", err)
        raise

    with open(default_config, "rb") as f:
        config_data = tomli.load(f)

    logging.info("config file path: %s", default_config)
    logging.warning("config data: %s", config_data)
    # Update configuration values
    config_data["serverAddr"] = config["serverAddr"]
    config_data["serverPort"] = config["serverPort"]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload frpc client."""
    if entry.entry_id not in hass.data.get(DOMAIN, {}):
        return True

    data = hass.data[DOMAIN].pop(entry.entry_id)
    process = data["process"]

    try:
        process.terminate()
        await hass.async_add_executor_job(process.wait, 5)
    except subprocess.TimeoutExpired:
        _LOGGER.warning("FRPC client did not terminate gracefully, forcing exit")
        process.kill()
    except Exception as err:
        _LOGGER.error("Error stopping FRPC client: %s", err)

    return True
