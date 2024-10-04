"""MSH patch funcs firebase funcs and small utils funcs."""

import asyncio
import base64
from http import HTTPStatus
import json
import os
from typing import Any

import aiofiles.os
import aiohttp
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import yaml

from . import config_core_secrets as ccs, msh_large_strings

MSH_CORE_BASE = "msh_core_base"
SERVER_ID = "msh_server_id"
SYS_DLIM = "msh_sys_dlim"
EXTERNAL_URL = "msh_external_url"


class ConfigFilePath:
    """Singleton class to store the configuration file path."""

    def __init__(self) -> None:
        """Initialize the configuration file path."""
        self.the_path: str = ""

    def set(self, config_file_path: str) -> None:
        """Set the configuration file path."""
        self.the_path = config_file_path

    def get(self) -> str:
        """Get the configuration file path."""
        return self.the_path

    async def create_custom_components_dir(self) -> None:
        """Create the custom_components/msh_core_base directory and required files."""
        custom_components_path = os.path.join(
            os.path.dirname(self.the_path), "custom_components", "msh_core_base"
        )
        os.makedirs(custom_components_path, exist_ok=True)

        # Define manifest.json content
        manifest_data = """{
    "domain": "msh_core_base",
    "name": "MSH Core Base",
    "version": "1.0.0"
}"""

        manifest_path = os.path.join(custom_components_path, "manifest.json")
        async with aiofiles.open(manifest_path, "w", encoding="utf-8") as manifest_file:
            await manifest_file.write(manifest_data)

        # Define __init__.py content
        init_content = """from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup(hass: HomeAssistant, config: dict):
    \"""Set up MSH Core Base.\"""
    if 'msh_core_base' not in config:
        return True

    conf = config['msh_core_base']

    # Your setup logic here using conf

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    \"""Set up MSH Core Base from a config entry.\"""
    # This is typically used with config flow; adjust according to needs.

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    \"""Unload an MSH Core Base entry.\"""
"""

        init_path = os.path.join(custom_components_path, "__init__.py")
        async with aiofiles.open(init_path, "w", encoding="utf-8") as init_file:
            await init_file.write(init_content)


# pylint: disable=redefined-outer-name
cf_path = ConfigFilePath()


def ignore_yaml_unknown_tags(
    loader: yaml.Loader, tag_suffix: str, node: yaml.Node
) -> None:
    """Ignore unknown YAML tags."""
    return


async def verify_secret_key(
    secret_key: str,
    home_name: str,
    name: str,
    email: str,
    password: str,
    internal_url: str,
) -> Any:
    """Verify the secret key with the cloud function."""
    cloud_function_url = "https://registernewuserandserver-jrskleaqea-uc.a.run.app"
    # cloud_function_url = "https://heroic.requestcatcher.com/"
    payload = {
        "secretKey": secret_key,
        "homeName": home_name,
        "name": name,
        "email": email,
        "pass": password,
        "internalUrl": internal_url,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(cloud_function_url, json=payload) as response:
                if response.status != HTTPStatus.OK:
                    if await response.json() is None:
                        return {
                            "success": False,
                            "message": f"Unexpected status code: {response.status}",
                        }
                    return await response.json()
                return await response.json()
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "message": f"Failed to connect to cloud function: {e!s}",
            }


async def sync_password_with_firebase(
    email: str, current_password: str, new_password: str
) -> None:
    """Sync password change with Firebase asynchronously."""

    encrypted_b64_new_pass = encrypt(new_password)

    encrypted_b64_current_pass = encrypt(current_password)

    # Build payload
    url = "https://updateuserpassword-jrskleaqea-uc.a.run.app"
    headers = {"Content-Type": "application/json"}
    serverId = await retrieve_value_from_config_file(SERVER_ID)
    payload = {
        "email": email,
        "currentPassword": encrypted_b64_current_pass,
        "newPassword": encrypted_b64_new_pass,
        "serverId": serverId,
    }

    async with (
        aiohttp.ClientSession() as session,
        session.post(url, headers=headers, json=payload) as response,
    ):
        if response.status != 200:
            response_data = await response.text()
            raise aiohttp.ClientError(
                f"Failed to sync with Firebase. Status: {response.status}, "
                f"Response: {response_data}"
            )


async def verify_user_subscription_for_this_server(username: str) -> Any:
    """Verify user's subscription status for a specific server."""
    from .auth.providers.homeassistant import (  # pylint: disable=import-outside-toplevel
        InternalServerError,
        NoInternetError,
        ServerDeniedError,
        SubscriptionOverError,
    )

    server_id = await retrieve_value_from_config_file(SERVER_ID)

    cloud_function_url = "https://checkSubscriptionByServer-jrskleaqea-uc.a.run.app"
    payload = {"email": username, "serverId": server_id}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(cloud_function_url, json=payload) as response:
                if response.status != HTTPStatus.OK:
                    response_data = await response.json()
                    error_key = response_data.get("error_key")

                    # Handle specific error scenarios
                    if error_key == "subscription_over":
                        raise SubscriptionOverError("Subscription has expired.")
                    if error_key == "server_denied":
                        raise ServerDeniedError(
                            "Server denied access or missing information."
                        )
                    if error_key == "server_crash":
                        raise InternalServerError("Internal server error occurred.")
                    raise ServerDeniedError(
                        f"Unexpected error: {response_data.get('message', 'Unknown error')}"
                    )

                response_data = await response.json()
                if response_data.get("success") is True:
                    return response_data.get("subscriptionEndDate")
                raise SubscriptionOverError("Success false")

        except aiohttp.ClientError as e:
            raise NoInternetError(f"Failed to connect to cloud function: {e!s}") from e


async def fetch_and_save_device_limit(email: str, server_id: str) -> None:
    """Fetch the device limit for a user and save it in a configuration file.

    Args:
        email (str): The user's email.
        server_id (str): The server ID.

    """

    cloud_function_url = "https://checkDeviceLimit-jrskleaqea-uc.a.run.app"
    payload = {"email": email, "serverId": server_id}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(cloud_function_url, json=payload) as response:
                if response.status == HTTPStatus.OK:
                    response_data = await response.json()
                    if response_data.get("success"):
                        device_limit = response_data.get("devicesLimit", 0)
                        encryptedBase64DevLimit = encrypt(str(device_limit))
                        await write_key_value_to_config_file(
                            SYS_DLIM, encryptedBase64DevLimit
                        )
        except aiohttp.ClientError:
            pass


async def write_key_value_to_config_file(key: str, value: str) -> None:
    """Write a value to the YAML configuration file under MSH_CORE_BASE section."""
    if not key.strip():
        raise ValueError("Key cannot be empty.")

    try:
        async with aiofiles.open(cf_path.get(), encoding="utf-8") as file:
            content = await file.read()
    except FileNotFoundError:
        content = ""

    lines = content.splitlines() if content else []
    found_section = False
    key_updated = False

    # If file is empty or no lines, create new structure
    if not lines:
        lines = [f"{MSH_CORE_BASE}:", f"  {key}: {value}"]
    else:
        # Look for MSH_CORE_BASE section and update/add key
        for i, line in enumerate(lines):
            if line.strip() == f"{MSH_CORE_BASE}:":
                found_section = True
                # Check next lines for existing key
                for j in range(i + 1, len(lines)):
                    if not lines[j].startswith(" ") and lines[j].strip():
                        lines.insert(j, f"  {key}: {value}")
                        key_updated = True
                        break
                    if lines[j].strip().startswith(f"{key}:"):
                        lines[j] = f"  {key}: {value}"
                        key_updated = True
                        break
                if not key_updated:
                    lines.insert(i + 1, f"  {key}: {value}")
                break

        # If section doesn't exist, add it at the end
        if not found_section:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend([f"{MSH_CORE_BASE}:", f"  {key}: {value}"])

    async with aiofiles.open(cf_path.get(), "w", encoding="utf-8") as file:
        await file.write("\n".join(lines) + "\n")


async def retrieve_value_from_config_file(key: str) -> str:
    """Retrieve a value from a file based on the key in the relative config directory.

    Args:
        key (str): Logical name of the file (e.g., 'server_id' for 'data_server_id.txt').

    Returns:
        str: The content of the file, or an empty string if the file doesn't exist or an error occurs.

    """
    try:
        # Read and return the value from the file
        async with aiofiles.open(cf_path.get(), encoding="utf-8") as file:
            content = await file.read()
            yaml.SafeLoader.add_multi_constructor("!", ignore_yaml_unknown_tags)  # type: ignore[no-untyped-call]
            data = yaml.safe_load(content)
            return str(data[MSH_CORE_BASE][key])
    except (FileNotFoundError, KeyError):
        return ""


def encrypt(data: str) -> str:
    """Encrypts a string using AES-CBC with PKCS7 padding and returns a base64-encoded string.

    Args:
        data (str): The plaintext data to encrypt.

    Returns:
        str: The base64-encoded encrypted string.

    """
    key = ccs.AES_ENC_KEY
    iv = ccs.AES_ENC_IV

    assert len(key) == 32, "Key must be 32 bytes for AES-256."
    assert len(iv) == 16, "IV must be 16 bytes for AES-CBC."

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    padder = padding.PKCS7(128).padder()

    data_bytes = data.encode("utf-8")
    padded_data = padder.update(data_bytes) + padder.finalize()
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

    return base64.b64encode(encrypted_data).decode("utf-8")


def decrypt(encrypted_data: str) -> str:
    """Decrypts a base64-encoded string encrypted using AES-CBC with PKCS7 padding.

    Args:
        encrypted_data (str): The base64-encoded encrypted string.

    Returns:
        str: The decrypted plaintext string.

    """
    key = ccs.AES_ENC_KEY
    iv = ccs.AES_ENC_IV

    assert len(key) == 32, "Key must be 32 bytes for AES-256."
    assert len(iv) == 16, "IV must be 16 bytes for AES-CBC."

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    unpadder = padding.PKCS7(128).unpadder()

    encrypted_bytes = base64.b64decode(encrypted_data)
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(encrypted_bytes) + decryptor.finalize()

    decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
    return decrypted_data.decode("utf-8")


async def add_external_url_into_confi_cors(external_url: str, config_path: str) -> None:
    """Add external URL to the CORS configuration file.

    Args:
        external_url (str): The external URL to add to the configuration.
        config_path (str): Path to the configuration file.

    """
    search_text = "http:\n  use_x_forwarded_for: true"
    replace_text = f"""http:
  cors_allowed_origins:
    - {external_url}
  use_x_forwarded_for: true"""

    try:
        async with aiofiles.open(config_path, encoding="utf-8") as file:
            content = await file.read()
        updated_content = content.replace(search_text, replace_text)
        async with aiofiles.open(config_path, mode="w", encoding="utf-8") as file:
            await file.write(updated_content)

    except FileNotFoundError:
        pass


async def reverse_proxy_client() -> None:
    """Run the bore client."""
    while True:
        try:
            await cf_path.create_custom_components_dir()
            # Read URL and port from the respective files
            external_url = await retrieve_value_from_config_file(EXTERNAL_URL)

            # Ensure both URL and port are available
            if external_url:
                # Construct the command
                # frpc http -s home1.msh.srvmysmarthomes.us -P 8002 -p websocket -n external_url -l 8123 -d external_url
                command = [
                    "frpc",
                    "http",
                    "-s",
                    "home1.msh.srvmysmarthomes.us",  # Updated server address
                    "-P",
                    "8002",  # Updated server port
                    "-p",
                    "websocket",  # Updated transport protocol
                    "-n",
                    external_url,  # Proxy name
                    "-l",
                    "8123",  # Local port
                    "-d",
                    external_url,  # Custom domain
                ]

                # Run the command asynchronously
                print("Starting connection...")  # noqa: T201
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                # Wait for the process to complete
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    print(f"Command failed with return code {process.returncode}")  # noqa: T201
                    print(f"stderr: {stderr.decode()}")  # noqa: T201
            else:
                print("URL or port information is missing. Please check the files.")  # noqa: T201
        except asyncio.CancelledError:
            print("Terminating the process...")  # noqa: T201
            break

        # Delay before retrying
        print("Rechecking in 8 seconds...")  # noqa: T201
        await asyncio.sleep(8)  # Adjust delay as necessary


def get_config_dir() -> str:
    """Extract dir from configuration.yaml path."""
    config_path = cf_path.get()
    return os.path.dirname(config_path)  # Extract config directory


async def ring_dashboard_create() -> None:
    """Create Ring Doc Page."""
    config_dir = get_config_dir()
    storage_dir = os.path.join(config_dir, ".storage")
    os.makedirs(storage_dir, exist_ok=True)
    dashboard_path = os.path.join(storage_dir, "lovelace_dashboards")
    ring_doc_path = os.path.join(storage_dir, "lovelace.help_ring_setup")

    if os.path.exists(ring_doc_path):
        return

    if os.path.exists(dashboard_path):
        return

    dashboard_registry = {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace_dashboards",
        "data": {
            "items": [
                {
                    "id": "help_ring_setup",
                    "show_in_sidebar": False,
                    "icon": "mdi:note-text",
                    "title": "Help Ring Setup",
                    "require_admin": True,
                    "mode": "storage",
                    "url_path": "help_ring_setup",
                }
            ]
        },
    }

    try:
        async with aiofiles.open(dashboard_path, "w", encoding="utf-8") as file:
            json.dump(dashboard_registry, file, indent=2)
    except (OSError, json.JSONDecodeError, PermissionError):
        return

    try:
        async with aiofiles.open(ring_doc_path, "w", encoding="utf-8") as file:
            json.dump(msh_large_strings.mshls_help_ring_setup, file, indent=2)
    except (OSError, json.JSONDecodeError, PermissionError):
        return
