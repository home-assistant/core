import httpx
import urllib.parse
import json
from typing import Any
from datetime import datetime, timedelta
from .const import (
    ANNOUNCEMENT_ENTITY_CONSTANT,
    ASSIGNMENT_ENTITY_CONSTANT,
    CONVERSATION_ENTITY_CONSTANT,
    GRADES_ENTITY_CONSTANT,
)

ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class CanvasAPI:
    """A wrapper for the Canvas API.

    This class provides methods to interact with the Canvas Learning Management System API.
    It supports various operations such as retrieving courses, assignments, announcements,
    and conversations.

    Attributes:
    host (str): The base URL of the Canvas instance.
    access_token (str): The API access token for authentication.
    """

    def __init__(self, host: str, access_token: str) -> None:
        """Initializes the CanvasAPI object with the host URL and access token.

        Args:
        host (str): The base URL of the Canvas instance.
        access_token (str): The API access token for authentication.
        """
        self.host = host
        self.access_token = access_token

    async def async_make_get_request(
        self, endpoint: str, parameters: dict = {}
    ) -> dict:
        """Makes an asynchronous GET request to a specified Canvas API endpoint.

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
        """Tests if the provided access token is valid by making a dummy request to the Canvas API.

        Returns:
        bool: True if the authentication is successful, False otherwise.
        """
        response = await self.async_make_get_request("/courses")

        return response.status_code == 200

    async def async_get_courses(self) -> list:
        """Retrieves a list of courses from the Canvas API.

        Returns:
        list: A list of courses.
        """
        response = await self.async_make_get_request("/courses", {"per_page": "50"})
        courses = json.loads(response.content.decode("utf-8"))
        return courses

    async def async_get_assignments(self, course_ids: list[str]) -> dict[str, Any]:
        """Retrieves a dictionary of assignments for given course IDs from the Canvas API.

        Args:
        course_ids (list[str]): A list of course IDs to fetch assignments from.

        Returns:
        dict: The response from the Canvas API.
        """
        assignments = {}

        for course_id in course_ids:
            response = await self.async_make_get_request(
                f"/courses/{course_id}/assignments",
                {"per_page": "50", "bucket": "future"},
            )
            course_assignments = json.loads(response.content.decode("utf-8"))
            for assignment in course_assignments:
                if "due_at" in assignment and assignment["due_at"] is not None:
                    due_date = datetime.strptime(
                        assignment["due_at"], ISO_DATETIME_FORMAT
                    )
                    next_two_weeks = datetime.utcnow() + timedelta(days=14)
                    if due_date <= next_two_weeks:
                        assignments[f"assignment-{assignment['id']}"] = assignment

        if len(assignments) != 0:
            return assignments
        else:
            return {f"assignment-{ASSIGNMENT_ENTITY_CONSTANT}": {}}

    async def async_get_announcements(self, course_ids: list[str]) -> dict[str, Any]:
        """Retrieves a dictionary of announcements for given course IDs from the Canvas API.

        Args:
        course_ids (list[str]): A list of course IDs to fetch assignments from.

        Returns:
        dict: The response from the Canvas API.
        """

        start_date = datetime.now() - timedelta(days=7)
        start_date_str = start_date.isoformat()
        end_date = datetime.now().isoformat()
        announcements = {}

        for course_id in course_ids:
            response = await self.async_make_get_request(
                "/announcements",
                {
                    "per_page": "50",
                    "context_codes": f"course_{course_id}",
                    "start_date": start_date_str,
                    "end_date": end_date,
                },
            )
            course_announcements = json.loads(response.content.decode("utf-8"))
            for announcement in course_announcements:
                announcements[f"announcement-{announcement['id']}"] = announcement

        if len(announcements) != 0:
            return announcements
        else:
            return {f"announcement-{ANNOUNCEMENT_ENTITY_CONSTANT}": {}}

    async def async_get_conversations(self) -> dict[str, Any]:
        """Retrieves a dictionary of conversations from the Canvas API.

        Returns:
        dict: The response from the Canvas API.
        """
        response_unread = await self.async_make_get_request(
            "/conversations", {"per_page": "50"}
        )
        conversations = json.loads(response_unread.content.decode("utf-8"))
        # get unreads and 5 latest reads
        read_conversations = [
            conv for conv in conversations if conv["workflow_state"] == "read"
        ]
        unread_conversations = [
            conv for conv in conversations if conv["workflow_state"] == "unread"
        ]
        read_conversations = read_conversations = sorted(
            read_conversations,
            key=lambda x: datetime.strptime(x["last_message_at"], ISO_DATETIME_FORMAT),
            reverse=True,
        )[:5]
        merged_conversations = read_conversations + unread_conversations
        if len(merged_conversations) != 0:
            return {
                f"conversation-{conversation['id']}": conversation
                for conversation in merged_conversations
            }
        else:
            return {f"conversation-{CONVERSATION_ENTITY_CONSTANT}": {}}

    async def async_get_grades(self, course_ids: list[str]) -> dict[str, Any]:
        """Retrieves a dictionary of submissions from the Canvas API.

        Returns:
        dict: The response from the Canvas API.
        """
        submissions = {}
        # Grades entity is right now meaningless because we dont get assignment description neither course name etc.
        # Check GRADES_KEY: CanvasSensorEntityDescription(.... (name_fn and value_fn))
        for course_id in course_ids:
            response = await self.async_make_get_request(
                f"/courses/{course_id}/students/submissions",
                {"per_page": "50"},
            )
            course_submissions = json.loads(response.content.decode("utf-8"))
            course_info_response = await self.async_make_get_request(
                f"/courses/{course_id}", {}
            )
            course_info = json.loads(course_info_response.content.decode("utf-8"))
            course_name = course_info.get("name", "Unknown Course")
            for submission in course_submissions:
                if submission["graded_at"] is not None:
                    graded_at = datetime.strptime(
                        submission["graded_at"], ISO_DATETIME_FORMAT
                    )
                    past_one_month = datetime.utcnow() - timedelta(days=30)
                    if graded_at >= past_one_month:
                        submission_details = {
                            "subject_name": course_name,
                            "assignment_name": submission.get("assignment_name", ""),
                            "score": submission.get("score", "Not Graded"),
                        }
                        submissions[
                            f"submission-{submission['id']}"
                        ] = submission_details

        if len(submissions) != 0:
            return submissions
        else:
            return {f"submission-{GRADES_ENTITY_CONSTANT}": {}}
