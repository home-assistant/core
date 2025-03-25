import subprocess
import logging
from pathlib import Path
import aiohttp
import tomli
from tomlkit import dumps, document, table, aot
from tomlkit.exceptions import TOMLKitError

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, EZLO_API_URI

_LOGGER = logging.getLogger(__name__)


def get_frp_config_path() -> str:
    """Return the frp client config path and ensure the directory and file exist."""
    config_dir = Path(__file__).parent / "config"
    config_path = config_dir / "frpc.toml"

    # Ensure the config directory exists
    if not config_dir.exists():
        _LOGGER.info("config folder missing! creating it now.")
        config_dir.mkdir(parents=True, exist_ok=True)

    # Ensure the config file exists
    if not config_path.exists():
        _LOGGER.info("frpc.toml file missing! creating it now.")
        config_path.touch()

    return config_path


def get_frp_binary_path() -> str:
    """Return the frp client binary path."""
    integration_dir = Path(__file__).parent
    bin_dir = integration_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    binary_path = bin_dir / "frpc"

    return binary_path


async def fetch_and_update_frp_config(
    hass: HomeAssistant, uuid: str, token: str
) -> bool:
    """Fetch and update the frp client config."""

    config_path = get_frp_config_path()

    try:
        # Fetch configuration from API
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{EZLO_API_URI}/api/user/{uuid}/server-config",
                timeout=10,
                headers={"Authorization": f"Bearer {token}"},
            ) as response,
        ):
            response.raise_for_status()
            api_config = await response.json()

        # Extract server configuration from nested structure
        server_config = api_config["serverConfig"]

        # Create TOML document with tomlkit
        def _create_toml():
            doc = document()

            # Add server configuration
            doc.add("serverAddr", server_config["serverAddr"])
            doc.add("serverPort", server_config["serverPort"])

            # Create array-of-tables for proxies
            proxies = aot()
            for proxy in server_config["proxies"]:
                proxy_table = table()
                proxy_table.add("name", proxy["name"])
                proxy_table.add("type", proxy["type"])
                proxy_table.add("localPort", proxy["localPort"])
                proxy_table.add(
                    "subdomain", proxy["subdomain"][: proxy["subdomain"].find(".")]
                )
                proxies.append(proxy_table)

            doc.add("proxies", proxies)

            # Write to file
            with open(config_path, "w") as f:
                f.write(dumps(doc))

        await hass.async_add_executor_job(_create_toml)
        return True

    except KeyError as err:
        _LOGGER.error("Missing expected key in API response: %s", err)
        raise
    except aiohttp.ClientError as err:
        _LOGGER.error("API request failed: %s", err)
        raise
    except Exception as err:
        _LOGGER.error("Configuration generation failed: %s", err)
        raise


async def start_frpc(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Start FRPC client service."""
    binary_path = get_frp_binary_path()
    config_path = get_frp_config_path()

    _LOGGER.info("Config: %s and binary path: %s", config_path, binary_path)

    try:
        process = await hass.async_add_executor_job(
            subprocess.Popen, [binary_path, "-c", config_path]
        )
    except Exception as err:
        _LOGGER.error("Configuration failed: %s", err)

    # Store process reference using entry.entry_id
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "process": process,
        "config_path": config_path,
        "binary_path": binary_path,
    }

    # Register cleanup with proper closure variables
    async def async_shutdown(event):
        await async_unload_entry(hass, config_entry)

    hass.bus.async_listen_once("homeassistant_stop", async_shutdown)


async def stop_frpc(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Stop FRPC client process."""

    def _sync_stop(process: subprocess.Popen) -> None:
        """Synchronously terminate the process."""
        try:
            if process.poll() is None:  # Process is still running
                process.terminate()
                try:
                    process.wait(5)  # Wait 5 seconds for clean exit
                except subprocess.TimeoutExpired:
                    _LOGGER.warning("FRPC client forced shutdown")
                    process.kill()
                    process.wait()  # Cleanup zombies
        except Exception as err:
            _LOGGER.error("Error stopping FRPC: %s", err)

    # Get stored process reference
    if config_entry.entry_id not in hass.data.get(DOMAIN, {}):
        _LOGGER.warning("FRPC process not found for entry %s", config_entry.entry_id)
        return

    data = hass.data[DOMAIN].get(config_entry.entry_id)
    if not data or "process" not in data:
        return

    process = data["process"]
    _LOGGER.info("Stopping FRPC client (PID: %s)", process.pid)

    try:
        await hass.async_add_executor_job(_sync_stop, process)
    except Exception as err:
        _LOGGER.error("Failed to stop FRPC: %s", err)
    finally:
        # Cleanup data entry
        hass.data[DOMAIN].pop(config_entry.entry_id, None)
        _LOGGER.debug("Cleaned up FRPC resources for entry %s", config_entry.entry_id)


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
