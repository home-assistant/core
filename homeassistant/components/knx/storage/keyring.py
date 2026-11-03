"""KNX Keyring handler."""

from collections.abc import Callable
import logging
from pathlib import Path
import shutil
from typing import Final

from xknx.exceptions.exception import InvalidSecureConfiguration
from xknx.secure.keyring import Keyring, sync_load_keyring

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import STORAGE_DIR

from ..const import DOMAIN, REPAIR_ISSUE_DATA_SECURE_GROUP_KEY

_LOGGER = logging.getLogger(__name__)


DEFAULT_KNX_KEYRING_FILENAME: Final = "keyring.knxkeys"


async def save_uploaded_knxkeys_file(
    hass: HomeAssistant,
    uploaded_file_id: str,
    password: str,
    is_usable: Callable[[Keyring], bool] | None = None,
) -> Keyring:
    """Validate the uploaded file and move it to the storage directory.

    Return a Keyring object. The uploaded file is discarded instead of
    replacing the stored one if `is_usable` rejects the keyring.
    Raises InvalidSecureConfiguration if the file or password is invalid.
    """

    def _process_upload() -> tuple[Keyring, bool]:
        with process_uploaded_file(hass, uploaded_file_id) as file_path:
            try:
                keyring = sync_load_keyring(
                    path=file_path,
                    password=password,
                )
            except InvalidSecureConfiguration as err:
                _LOGGER.debug(err)
                raise
            if is_usable is not None and not is_usable(keyring):
                return keyring, False
            dest_path = Path(hass.config.path(STORAGE_DIR, DOMAIN))
            dest_path.mkdir(exist_ok=True)
            dest_file = dest_path / DEFAULT_KNX_KEYRING_FILENAME
            shutil.move(file_path, dest_file)
        return keyring, True

    keyring, stored = await hass.async_add_executor_job(_process_upload)

    if stored:
        # If there is an existing DataSecure group key issue, remove it.
        # GAs might not be DataSecure anymore after uploading a valid keyring,
        # if they are, we raise the issue again when receiving a telegram.
        ir.async_delete_issue(hass, DOMAIN, REPAIR_ISSUE_DATA_SECURE_GROUP_KEY)

    return keyring


async def load_stored_knxkeys_file(
    hass: HomeAssistant, filename: str, password: str
) -> Keyring:
    """Load a keyring file from the storage directory.

    Raises InvalidSecureConfiguration if the file or password is invalid
    and FileNotFoundError if the file is missing.
    """
    path = Path(hass.config.path(STORAGE_DIR, filename))
    return await hass.async_add_executor_job(sync_load_keyring, path, password)
