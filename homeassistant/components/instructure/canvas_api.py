import httpx
import urllib.parse
import json
from typing import Any


class CanvasAPI:
    """
    A wrapper for the Canvas API.

    This class provides methods to interact with the Canvas Learning Management System API.
    It supports various operations such as retrieving courses, assignments, announcements,
    and conversations.

    Attributes:
    host (str): The base URL of the Canvas instance.
    access_token (str): The API access token for authentication.
    """

    def __init__(self, host: str, access_token: str) -> None:
        """
        Initializes the CanvasAPI object with the host URL and access token.

        Args:
        host (str): The base URL of the Canvas instance.
        access_token (str): The API access token for authentication.
        """
        self.host = host
        self.access_token = access_token

    async def async_make_get_request(
        self, endpoint: str, parameters: dict = {}
    ) -> dict:
        """
        Makes an asynchronous GET request to a specified Canvas API endpoint.

        Args:
        endpoint (str): The API endpoint to make the request to.
        parameters (dict, optional): Query parameters to include in the request. Defaults to {}.

        Returns:
        dict: The response from the Canvas API.
        """

        headers = {"Authorization": "Bearer " + self.access_token}
        parameters_string = urllib.parse.urlencode(parameters)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.host + endpoint + "?" + parameters_string, headers=headers
            )

        return response

    async def async_test_authentication(self) -> bool:
        """
        Tests if the provided access token is valid by making a dummy request to the Canvas API.

        Returns:
        bool: True if the authentication is successful, False otherwise.
        """
        response = await self.async_make_get_request("/courses")

        return response.status_code == 200

    async def async_get_courses(self) -> list:
        """
        Retrieves a list of courses from the Canvas API.

        Returns:
        list: A list of courses.
        """
        response = await self.async_make_get_request("/courses", {"per_page": "50"})
        courses = json.loads(response.content.decode("utf-8"))
        return courses

    async def async_get_assignments(self, course_ids: list[str]) -> dict[str, Any]:
        """
        Retrieves a dictionary of assignments for given course IDs from the Canvas API.

        Args:
        course_ids (list[str]): A list of course IDs to fetch assignments from.

        Returns:
        dict: The response from the Canvas API.
        """
        assignments = {}

        for course_id in course_ids:
            response = await self.async_make_get_request(
                f"/courses/{course_id}/assignments", {"per_page": "50"}
            )
            course_assignments = json.loads(response.content.decode("utf-8"))
            for assignment in course_assignments:
                assignments[assignment["id"]] = assignment

        return assignments

    async def async_get_announcements(self, course_ids: list[str]) -> dict[str, Any]:
        """
        Retrieves a dictionary of announcements for given course IDs from the Canvas API.

        Args:
        course_ids (list[str]): A list of course IDs to fetch assignments from.

        Returns:
        dict: The response from the Canvas API.
        """
        announcements = {}

        for course_id in course_ids:
            response = await self.async_make_get_request(
                "/announcements",
                {"per_page": "50", "context_codes": f"course_{course_id}"},
            )
            course_announcements = json.loads(response.content.decode("utf-8"))
            for announcement in course_announcements:
                announcements[announcement["id"]] = announcement

        return announcements

    async def async_get_conversations(self) -> dict[str, Any]:
        """
        Retrieves a dictionary of conversations from the Canvas API.

        Returns:
        dict: The response from the Canvas API.
        """
        response = await self.async_make_get_request(
            "/conversations", {"per_page": "50"}
        )
        conversations = json.loads(response.content.decode("utf-8"))
        return {conversation["id"]: conversation for conversation in conversations}
