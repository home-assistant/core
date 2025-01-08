"""Notification service for Google Mail integration."""

from __future__ import annotations

import base64
import mimetypes
import os
import requests
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import AsyncConfigEntryAuth
from .const import (
    ATTR_BCC,
    ATTR_CC,
    ATTR_FROM,
    ATTR_ME,
    ATTR_SEND,
    DATA_AUTH,
    ATTR_HTML,
    ATTR_IMAGES,
    ATTR_FILES,
    ATTR_FILE_KIND_IMAGE,
    ATTR_FILE_KIND_FILE,
    ATTR_FILE_PATH,
    ATTR_FILE_NAME,
    ATTR_FILE_URL,
    ATTR_FILE_MIME_TYPE,
    ATTR_FILE_CONTENT,
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> GMailNotificationService | None:
    """Get the notification service."""
    return GMailNotificationService(discovery_info) if discovery_info else None


class GMailNotificationService(BaseNotificationService):
    """Define the Google Mail notification logic."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the service."""
        self.auth: AsyncConfigEntryAuth = config[DATA_AUTH]

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists on disk and is in an authorized path."""
        return self.hass.config.is_allowed_path(filename) and os.path.isfile(filename)

    def read_file(self, file_path: str) -> bytes:
        """Read a file's content in a blocking manner."""
        try:
            # Open the file in binary mode and read its content
            with open(file_path, "rb") as file:
                return file.read()

        except FileNotFoundError:
            # Handle case where the file does not exist
            raise FileNotFoundError(f"Error: The file at {file_path} was not found.")

        except PermissionError:
            # Handle case where there's a permission error
            raise PermissionError(
                f"Error: Permission denied to access the file at {file_path}."
            )

        except IOError as e:
            # Handle other IO-related errors (e.g., disk errors)
            raise IOError(f"An I/O error occurred while reading the file: {e}")

        except Exception as e:
            # Catch any other exceptions that might occur
            raise RuntimeError(f"An unexpected error occurred: {e}")

    def fetch_url(self, url: str) -> bytes:
        """Make the request in a blocking manner."""
        try:
            # Send GET request to the URL
            response = requests.get(url)

            # Raise an exception for HTTP errors (4xx, 5xx responses)
            response.raise_for_status()

            # Return the response content if no errors occurred
            return response.content
        except requests.exceptions.RequestException as e:
            # Catch any RequestException (including connection errors, timeouts, etc.)
            raise requests.exceptions.ConnectionError(f"An error occurred: {e}")

        except Exception as e:
            # Catch other general exceptions
            raise RuntimeError(f"An unexpected error occurred: {e}")

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message."""
        data: dict[str, Any] = kwargs.get(ATTR_DATA) or {}
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        if any(attr in data for attr in [ATTR_HTML, ATTR_IMAGES, ATTR_FILES]):
            email = MIMEMultipart(_subtype="related")
            html_content = data.get(ATTR_HTML, message)
            email.attach(MIMEText(html_content, "html"))

            for image in data.get(ATTR_IMAGES, []):
                await self.attach_file(email, image, ATTR_FILE_KIND_IMAGE)

            for file in data.get(ATTR_FILES, []):
                await self.attach_file(email, file)
        else:
            email = MIMEText(message, "html")

        if to_addrs := kwargs.get(ATTR_TARGET):
            email["To"] = ", ".join(to_addrs)

        email["From"] = data.get(ATTR_FROM, ATTR_ME)
        email["Subject"] = title
        email[ATTR_CC] = ", ".join(data.get(ATTR_CC, []))
        email[ATTR_BCC] = ", ".join(data.get(ATTR_BCC, []))

        encoded_message = base64.urlsafe_b64encode(email.as_bytes()).decode()
        body = {"raw": encoded_message}
        users = (await self.auth.get_resource()).users()

        if data.get(ATTR_SEND) is False:
            msg = users.drafts().create(userId=email["From"], body={ATTR_MESSAGE: body})
        else:
            if not to_addrs:
                raise ValueError("Recipient address required")
            msg = users.messages().send(userId=email["From"], body=body)

        await self.hass.async_add_executor_job(msg.execute)

    async def attach_file(
        self, email: MIMEMultipart, item: dict, kind: str = ATTR_FILE_KIND_FILE
    ) -> None:
        """Append a file or image to the email message."""
        file_data = await self.process_file(item, kind)

        if kind == ATTR_FILE_KIND_IMAGE:
            attachment = MIMEImage(
                file_data["content"], _subtype=file_data["mime_type"].split("/")[-1]
            )
        else:
            attachment = MIMEBase(
                file_data["mime_type"].split("/")[0],
                file_data["mime_type"].split("/")[1],
            )
            attachment.set_payload(file_data["content"])

        attachment.add_header(
            "Content-Disposition", "attachment", filename=file_data["file_name"]
        )
        attachment.add_header("Content-ID", file_data["file_name"])

        encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition", f'attachment; filename="{file_data["file_name"]}"'
        )

        email.attach(attachment)

    async def process_file(self, item: dict, kind: str) -> dict:
        """Process file data based on its type."""
        if ATTR_FILE_PATH in item:
            file_path = item[ATTR_FILE_PATH]
            if not self.file_exists(file_path):
                raise FileNotFoundError(f"File does not exist: {file_path}")

            content = await self.hass.async_add_executor_job(self.read_file, file_path)
            file_name = item.get(ATTR_FILE_NAME, os.path.basename(file_path))
            mime_type = item.get(
                ATTR_FILE_MIME_TYPE,
                mimetypes.guess_type(file_name)[0] or "application/octet-stream",
            )
        elif ATTR_FILE_URL in item:
            url = item[ATTR_FILE_URL]
            content = await self.hass.async_add_executor_job(self.fetch_url, url)
            file_name = item.get(ATTR_FILE_NAME, os.path.basename(url))
            mime_type = item.get(
                ATTR_FILE_MIME_TYPE,
                mimetypes.guess_type(file_name)[0] or "application/octet-stream",
            )
        elif ATTR_FILE_CONTENT in item:
            content = str(item[ATTR_FILE_CONTENT]).encode("utf-8")
            file_name = item.get(ATTR_FILE_NAME, "file.dat")
            mime_type = item.get(ATTR_FILE_MIME_TYPE, "application/octet-stream")
        else:
            raise ValueError("File must include one of path, url, or content.")

        return {"content": content, "file_name": file_name, "mime_type": mime_type}
