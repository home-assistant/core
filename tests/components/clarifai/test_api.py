"""Tests for the Clarifai API."""
from clarifai_grpc.grpc.api import resources_pb2, service_pb2
from clarifai_grpc.grpc.api.status import status_code_pb2
import pytest

from homeassistant.components.clarifai.api import Clarifai, validate_response
from homeassistant.exceptions import HomeAssistantError

from tests.async_mock import MagicMock, patch


class TestClarifaiAPI:
    """Test class for Clarifai API."""

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.access_token = "12345678abcdef"

        with patch(
            "clarifai_grpc.grpc.api.service_pb2_grpc.V2Stub", return_value=MagicMock()
        ):
            self.api = Clarifai(self.access_token)

    @patch(
        "homeassistant.components.clarifai.api.validate_response", return_value=False,
    )
    def test_post_workflow_results(self, mock_validation):
        """Test the post_workflow_results method of the Clarifai API."""
        app_id = "12345678abcdef"
        workflow_id = "Face"
        result_format = "default"
        image_bytes = b"Test"

        request = service_pb2.PostWorkflowResultsRequest(
            user_app_id=resources_pb2.UserAppIDSet(app_id=app_id),
            workflow_id=workflow_id,
            inputs=[
                resources_pb2.Input(
                    data=resources_pb2.Data(
                        image=resources_pb2.Image(base64=image_bytes)
                    )
                )
            ],
        )
        metadata = (("authorization", f"Key {self.access_token}"),)

        self.api.post_workflow_results(app_id, workflow_id, result_format, image_bytes)

        self.api.stub.PostWorkflowResults.assert_called_once_with(
            request, metadata=metadata
        )


def test_validate_response_successful():
    """Test the successful path of validate_response."""
    response = MagicMock()
    response.status.code = status_code_pb2.SUCCESS

    assert validate_response(response) is True


def test_validate_response_failure():
    """Test the failure path of validate_response."""
    response = MagicMock()
    response.status.code = status_code_pb2.FAILURE

    with pytest.raises(HomeAssistantError):
        validate_response(response)


# def test_parse_workflow_response_default():

# def test_parse_workflow_response_concepts():

# def test_parse_workflow_response_no_response():
