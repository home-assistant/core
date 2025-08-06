from collections.abc import Callable
from functools import wraps
import logging
from pathlib import Path
import random
import sys
import threading
import time
from typing import TypeVar

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from anki.collection import Collection
from anki.errors import SyncError

from .const import DEFAULT_HOST

logger = logging.getLogger(__name__)

FunctionT = TypeVar("FunctionT", bound=Callable)


def run_in_thread(func: FunctionT) -> FunctionT:
    """Run a function in a thread."""

    @wraps(func)
    def decorator(*args, **kwargs):
        val = None

        def thread_func(*args, **kwargs):
            nonlocal val
            val = func(*args, **kwargs)

        thread = threading.Thread(target=thread_func, args=args, kwargs=kwargs)

        exc: BaseException | None = None

        def invoke_excepthook(_thread: threading.Thread) -> None:
            nonlocal exc
            exc = sys.exc_info()[1]

        thread._invoke_excepthook = invoke_excepthook  # noqa: SLF001
        thread.start()
        thread.join()
        if exc:
            raise exc
        return val

    return decorator


class AnkiDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config):
        super().__init__(hass, logger, name="Anki")
        self.config = config
        # Normalize the collection path
        self.col_path = hass.config.path(
            "anki/" + self._get_unique_id() + "/collection.anki2"
        )
        Path(self.col_path).parent.mkdir(parents=True, exist_ok=True)
        self.col = Collection(self.col_path)

    def _get_unique_id(self):
        """Return a unique ID for the coordinator."""
        return slugify(
            f"{self.config[CONF_USERNAME]}"
            + (
                f" on {self.config[CONF_HOST]}"
                if self.config[CONF_HOST] != DEFAULT_HOST
                else ""
            )
        )

    @run_in_thread
    def sync(self) -> None:
        """
        Sync the flashcards.

        Raises:
            SyncError: if an error occurs during sync.

        """
        endpoint = self.config[CONF_HOST]

        # Retry if multiple programs are connecting to the same account in the same time
        while True:
            try:
                auth = self.col.sync_login(
                    self.config[CONF_USERNAME],
                    self.config[CONF_PASSWORD],
                    endpoint=endpoint,
                )
                output = self.col.sync_collection(auth, True)
                status = self.col.sync_status(auth)

                # https://github.com/ankitects/anki/blob/a515463/qt/aqt/sync.py#L93
                if output.new_endpoint:
                    endpoint = output.new_endpoint

                if output.server_message:
                    raise SyncError(output.server_message)

                if status.required == status.NO_CHANGES:
                    return

                auth = self.col.sync_login(
                    self.config[CONF_USERNAME],
                    self.config[CONF_PASSWORD],
                    endpoint=endpoint,
                )
                self.col.full_upload_or_download(
                    auth=auth,
                    server_usn=getattr(output, "server_media_usn", None),
                    upload=False,
                )
            except SyncError as err:
                if "try again" in str(err).lower():
                    seconds = random.randint(0, 30)
                    logger.warning(f"Error during sync: {type(err).__name__}: {err}")
                    logger.warning(
                        f"Too many connections, retrying in {seconds} seconds..."
                    )
                    time.sleep(seconds)
                    continue
                raise
            break

    async def _async_update_data(self) -> dict[str, int]:
        self.sync()
        counts = {
            "new": 0,
            "learn": 0,
            "review": 0,
        }
        for deck in self.col.sched.deck_due_tree().children:
            counts["new"] += deck.new_count
            counts["learn"] += deck.learn_count
            counts["review"] += deck.review_count
        return counts
