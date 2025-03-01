"""Utils for the Slack integration."""

import logging

import aiofiles
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

_LOGGER = logging.getLogger(__name__)


async def upload_file_to_slack(
    client: AsyncWebClient,
    channel_ids: list[str | None],
    file_content: bytes | str | None,
    filename: str,
    title: str | None,
    message: str,
    thread_ts: str | None,
    file_path: str | None = None,  # Allow passing a file path
) -> None:
    """Upload a file to Slack for the specified channel IDs.

    Args:
        client (AsyncWebClient): The Slack WebClient instance.
        channel_ids (list[str | None]): List of channel IDs to upload the file to.
        file_content (Union[bytes, str, None]): Content of the file (local or remote). If None, file_path is used.
        filename (str): The file's name.
        title (str | None): Title of the file in Slack.
        message (str): Initial comment to accompany the file.
        thread_ts (str | None): Thread timestamp for threading messages.
        file_path (str | None): Path to the local file to be read if file_content is None.

    Raises:
        SlackApiError: If the Slack API call fails.
        OSError: If there is an error reading the file.

    """
    if file_content is None and file_path:
        # Read file asynchronously if file_content is not provided
        try:
            async with aiofiles.open(file_path, "rb") as file:
                file_content = await file.read()
        except OSError as os_err:
            _LOGGER.error("Error reading file %s: %r", file_path, os_err)
            return

    for channel_id in channel_ids:
        try:
            await client.files_upload_v2(
                channel=channel_id,
                file=file_content,
                filename=filename,
                title=title or filename,
                initial_comment=message,
                thread_ts=thread_ts or "",
            )
            _LOGGER.info("Successfully uploaded file to channel %s", channel_id)
        except SlackApiError as err:
            _LOGGER.error(
                "Error while uploading file to channel %s: %r", channel_id, err
            )
