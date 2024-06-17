"""ics upload handler."""

from pathlib import Path
import shutil

from ical.calendar_stream import CalendarStream
from ical.exceptions import CalendarParseError

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from ..const import STORAGE_PATH


async def save_uploaded_ics_file(
    hass: HomeAssistant, uploaded_file_id: str, storage_key: str
):
    """Validate the uploaded file and move it to the storage directory."""

    def _process_upload():
        with process_uploaded_file(hass, uploaded_file_id) as file:
            ics = file.read_text(encoding="utf8")
            try:
                CalendarStream.from_ics(ics)
            except CalendarParseError as err:
                raise ConfigEntryNotReady(
                    "Failed to upload file: Invalid ICS file"
                ) from err
            dest_path = Path(hass.config.path(STORAGE_PATH.format(key=storage_key)))
            shutil.move(file, dest_path)

    return await hass.async_add_executor_job(_process_upload)
