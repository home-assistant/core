"""warnings."""
from typing import Any

from .downloader import SmhiDownloader
from .smhi_geolocation_event import SmhiGeolocationEvent


class SmhiWarnings:
    """SmhiWarning."""

    async def get_warnings(self) -> list[SmhiGeolocationEvent]:
        """Get warning data from smhi api."""
        warnings_url = (
            "https://opendata-download-warnings.smhi.se/ibww/api/version/1/warning.json"
        )
        smhi_downloader = SmhiDownloader()
        data = await smhi_downloader.download_json(warnings_url)

        if isinstance(data, list):
            return self.parse_warnings(data)
        return []

    def parse_warnings(self, data: list[dict[str, Any]]) -> list[SmhiGeolocationEvent]:
        """Parse warning data from smhi api."""
        geo_location_entities = []

        warnings = []

        for warning in data:
            parsed_warning = {
                "id": warning.get("id"),
                "normalProbability": warning.get("normalProbability"),
                "event": warning.get("event", {}),
                "descriptions": warning.get("descriptions", []),
            }
            parsed_warning["warningAreas"] = []
            for area in warning.get("warningAreas", []):
                parsed_area = {
                    "id": area.get("id"),
                    "approximateStart": area.get("approximateStart"),
                    "approximateEnd": area.get("approximateEnd"),
                    "published": area.get("published"),
                    "normalProbability": area.get("normalProbability"),
                    "areaName": area.get("areaName", {}),
                    "warningLevel": area.get("warningLevel", {}),
                    "eventDescription": area.get("eventDescription", {}),
                    "affectedAreas": area.get("affectedAreas", []),
                    "descriptions": area.get("descriptions", []),
                    "geometry": area.get("area", {})
                    .get("features", [{}])[0]
                    .get("geometry", {}),
                }
                parsed_warning["warningAreas"].append(parsed_area)

            warnings.append(parsed_warning)

        for warning in warnings:
            name = str(warning["warningAreas"][0]["descriptions"][0]["text"]["en"])

            if "coordinates" in warning["warningAreas"][0]["geometry"]:
                if len(warning["warningAreas"][0]["geometry"]["coordinates"]) == 1:
                    for location in warning["warningAreas"][0]["geometry"][
                        "coordinates"
                    ][0]:
                        geo_location_entities.append(
                            SmhiGeolocationEvent(name, location[1], location[0])
                        )
                else:
                    for location in warning["warningAreas"][0]["geometry"][
                        "coordinates"
                    ]:
                        geo_location_entities.append(
                            SmhiGeolocationEvent(name, location[1], location[0])
                        )

        return geo_location_entities
