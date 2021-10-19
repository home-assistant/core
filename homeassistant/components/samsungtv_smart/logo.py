
import aiohttp
import aiofiles
import asyncio
import json
import logging
import numpy as np
import os
import re
import traceback

from datetime import timedelta, datetime
from enum import Enum
from typing import Optional


# Logo feature constants
class LogoOption(Enum):
    Disabled = 1
    WhiteColor = 2
    BlueColor = 3
    BlueWhite = 4
    DarkWhite = 5
    TransparentColor = 6
    TransparentWhite = 7


LOGO_OPTIONS_MAPPING = {
    LogoOption.Disabled: "none",
    LogoOption.WhiteColor: "fff-color",
    LogoOption.BlueColor: "05a9f4-color",
    LogoOption.BlueWhite: "05a9f4-white",
    LogoOption.DarkWhite: "282c34-white",
    LogoOption.TransparentColor: "transparent-color",
    LogoOption.TransparentWhite: "transparent-white",
}
LOGO_OPTION_DEFAULT = [LogoOption.WhiteColor.value, "fff-color"]
LOGO_BASE_URL = "https://jaruba.github.io/channel-logos/"
LOGO_FILE = "logo_paths.json"
LOGO_FILE_DOWNLOAD = "logo_paths_download.json"
LOGO_FILE_DAYS_BEFORE_UPDATE = 1
LOGO_MIN_SCORE_REQUIRED = 60
LOGO_MEDIATITLE_KEYWORD_REMOVAL = ["HDTV", "HD"]
LOGO_MAX_PATHS = 30000

_LOGGER = logging.getLogger(__name__)


class Logo:
    """ Class that fetches logos for Samsung TV Tizen. Works with https://github.com/jaruba/channel-logos. """

    def __init__(
        self,
        logo_option: int,
        logo_file_download: str = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self._media_image_base_url = None
        self._logo_option = None
        self.set_logo_color(logo_option)
        if session:
            self._session = session
        else:
            self._session = aiohttp.ClientSession()

        self._last_check = None

        app_path = os.path.dirname(os.path.realpath(__file__))
        self._logo_file_path = os.path.join(app_path, LOGO_FILE)
        self._logo_file_download_path = (
            logo_file_download or
            os.path.join(app_path, LOGO_FILE_DOWNLOAD)
        )

    def set_logo_color(self, logo_option):
        """ Sets the logo color option and image base url if not already set to this option """
        logo_option = (
            LOGO_OPTIONS_MAPPING[LogoOption(logo_option)]
            if logo_option
            else LOGO_OPTION_DEFAULT[1]
        )
        if self._logo_option != logo_option:
            _LOGGER.debug("Setting logo option to %s", logo_option)
            if logo_option in LOGO_OPTIONS_MAPPING.values():
                if logo_option == "none":
                    self._media_image_base_url = None
                else:
                    self._media_image_base_url = "{}export/{}".format(
                        LOGO_BASE_URL, logo_option
                    )
                self._logo_option = logo_option
            else:
                _LOGGER.warning(
                    "Unrecognized value '%s' for 'Display logos' option. Using default value.",
                    logo_option,
                )
                self._logo_option = LOGO_OPTION_DEFAULT[1]
                self._media_image_base_url = "{}export/{}".format(
                    LOGO_BASE_URL, LOGO_OPTION_DEFAULT[1]
                )

    async def _async_ensure_latest_path_file(self):
        """ Does check if logo paths file exists and if it does - is it out of date or not. """
        if (
            self._last_check is not None and
            self._last_check > datetime.now().astimezone()-timedelta(days=LOGO_FILE_DAYS_BEFORE_UPDATE)
        ):
            return
        if self._media_image_base_url is not None:
            if os.path.isfile(self._logo_file_download_path):
                file_date = datetime.utcfromtimestamp(
                    os.path.getmtime(self._logo_file_download_path)
                ).astimezone()
                if file_date < (
                    datetime.now().astimezone()
                    - timedelta(days=LOGO_FILE_DAYS_BEFORE_UPDATE)
                ):
                    try:
                        async with self._session.head(
                            LOGO_BASE_URL + "logo_paths.json"
                        ) as response:
                            url_date = datetime.strptime(
                                response.headers.get("Last-Modified"),
                                "%a, %d %b %Y %X %Z",
                            ).astimezone()
                            if url_date > file_date:
                                self._last_check = datetime.now().astimezone()
                                await self._download_latest_path_file()
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        _LOGGER.warning(
                            "Not able to check for latest paths file for logos from %s%s. "
                            "Check if the URL is accessible from this machine",
                            LOGO_BASE_URL,
                            "logo_paths.json",
                        )
            else:
                self._last_check = datetime.now().astimezone()
                await self._download_latest_path_file()

    async def _download_latest_path_file(self):
        try:
            async with self._session.get(LOGO_BASE_URL + "logo_paths.json") as response:
                response = (await response.read()).decode("utf-8")
                if response:
                    async with aiofiles.open(
                        self._logo_file_download_path, mode="w+", encoding="utf-8"
                    ) as paths_file:
                        await paths_file.write(response)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.warning(
                "Not able to download latest paths file for logos from %s%s. "
                "Check if the URL is accessible from this machine.",
                LOGO_BASE_URL,
                "logo_paths.json",
            )
        except PermissionError:
            _LOGGER.warning(
                "No permission while trying to write the downloaded paths file to %s. "
                "Please check file writing permissions.",
                self._logo_file_download_path,
            )
        except OSError as e:
            _LOGGER.warning(
                "Not able to write to write the downloaded paths file to %s. "
                "Disk might be full or another OS error occurred",
                self._logo_file_download_path,
            )
            _LOGGER.warning(traceback.print_exc())      

    async def async_find_match(self, media_title):
        """ Finds a match in the logo_paths file for a given media_title """
        if media_title is None:
            _LOGGER.warning("No media title right now! Not able to find a matching logo.")
            return
        if self._media_image_base_url is None:
            _LOGGER.warning("Media image base url was not set! Not able to find a matching logo.")
            return
        _LOGGER.debug("Matching media title for %s", media_title)
        await self._async_ensure_latest_path_file()

        # remove string between parenthesis ()
        removal = re.finditer(r"\((.*?)\)", media_title)
        for match in removal:
            media_title = media_title.replace(match.group(), "")

        # remove specific strings
        for word in LOGO_MEDIATITLE_KEYWORD_REMOVAL:
            media_title = media_title.lower().replace(word.lower(), "")

        # remove leading and trailing spaces
        media_title = media_title.lower().strip()

        try:
            if os.path.isfile(self._logo_file_download_path):
                async with aiofiles.open(self._logo_file_download_path, "r") as f:
                    image_paths = iter(json.loads(await f.read()).items())
            elif os.path.isfile(self._logo_file_path):
                async with aiofiles.open(self._logo_file_path, "r") as f:
                    image_paths = iter(json.loads(await f.read()).items())
            best_match = {"ratio": None, "title": None, "path": None}

            paths_checked = 0
            for image_path in image_paths:
                if paths_checked > LOGO_MAX_PATHS:
                    _LOGGER.warning(
                        "Exceeded maximum amount of paths (%d) while searching for a match. Halting the search.",
                        LOGO_MAX_PATHS,
                    )
                    break
                ratio = self._levenshtein_ratio(media_title, image_path[0].lower())
                if best_match["ratio"] is None or ratio > best_match["ratio"]:
                    best_match = {
                        "ratio": ratio,
                        "title": image_path[0],
                        "path": image_path[1],
                    }
                if best_match["ratio"] == 1:
                    break
                paths_checked += 1

            if best_match["ratio"] >= LOGO_MIN_SCORE_REQUIRED / 100:
                _LOGGER.debug(
                    "Match found for %s: %s (%f) %s",
                    media_title,
                    best_match["title"],
                    best_match["ratio"],
                    self._media_image_base_url + best_match["path"],
                )
                return self._media_image_base_url + best_match["path"]

            _LOGGER.debug(
                "No match found for %s: best candidate was %s (%f) %s",
                media_title,
                best_match["title"],
                best_match["ratio"],
                self._media_image_base_url + best_match["path"],
            )
            return None
        except:
            _LOGGER.warning(
                "Not able to search for a logo. Logo paths file might be missing at %s or %s.",
                self._logo_file_download_path,
                self._logo_file_path,
            )
            return None


    @staticmethod
    def _levenshtein_ratio(s, t):
        rows = len(s) + 1
        cols = len(t) + 1
        distance = np.zeros((rows, cols), dtype=int)

        for i in range(1, rows):
            for k in range(1, cols):
                distance[i][0] = i
                distance[0][k] = k

        for col in range(1, cols):
            for row in range(1, rows):
                if s[row - 1] == t[col - 1]:
                    cost = 0
                else:
                    cost = 2
                distance[row][col] = min(
                    distance[row - 1][col] + 1,
                    distance[row][col - 1] + 1,
                    distance[row - 1][col - 1] + cost,
                )

        ratio = ((len(s) + len(t)) - distance[row][col]) / (len(s) + len(t))
        return ratio
