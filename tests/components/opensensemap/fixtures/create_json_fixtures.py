"""Create the fixture json files needed for testing opensensemap."""
import asyncio
import json
import os

import aiohttp
from opensensemap_api import OpenSenseMap

from tests.components.opensensemap import VALID_STATION_ID

THIS_DIR = os.path.dirname(__file__)

SENSOR_TEST_IDS = {"valid": VALID_STATION_ID, "invalid": "invlaid-sensor"}


async def dump_api_responses_to_json_files():
    """Sample code to retrieve the data from an OpenSenseMap station."""
    async with aiohttp.ClientSession() as session:
        for test_case, sensor_id in SENSOR_TEST_IDS.items():
            station = OpenSenseMap(sensor_id, session)
            await station.get_data()
            with open(
                os.path.join(THIS_DIR, f"{test_case}.json"),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(station.data, f)


if __name__ == "__main__":
    asyncio.run(dump_api_responses_to_json_files())
