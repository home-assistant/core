"""Tests for the Clarifai API."""
from clarifai_grpc.grpc.api import resources_pb2, service_pb2
from google.protobuf.json_format import Parse
import pytest

from homeassistant.components.clarifai.api import Clarifai
from homeassistant.components.clarifai.const import CONCEPTS, DEFAULT, OUTPUTS
from homeassistant.exceptions import HomeAssistantError

from tests.async_mock import MagicMock, patch
from tests.common import load_fixture

DATA = "data"
NAME = "name"
VALUE = "value"


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
        "homeassistant.components.clarifai.api._validate_response", return_value=False,
    )
    def test_post_workflow_results_request_logic(self, mock_validation):
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

    def test_post_workflow_results_response_with_default_parser(self):
        """Test the default response parsing methods of post_workflow_results."""
        result_format = DEFAULT

        message = Parse(
            load_fixture("clarifai/response_success.json"),
            service_pb2.PostWorkflowResultsResponse(),
        )

        self.api.stub.PostWorkflowResults.return_value = message

        result = self.api.post_workflow_results(
            "12345678abcdef", "General", result_format, b"Test"
        )

        concept_name = "dog"
        concept_value = 0.9979874
        found_dog = False

        assert OUTPUTS in result
        for output in result[OUTPUTS]:
            assert DATA in output
            output_data = output[DATA]
            if CONCEPTS in output_data:
                for concept in output_data[CONCEPTS]:
                    assert NAME in concept
                    assert VALUE in concept
                    if concept[NAME] == concept_name:
                        found_dog = True
                        assert concept[VALUE] == pytest.approx(concept_value)
        assert found_dog

    def test_post_workflow_results_response_with_concepts_parser(self):
        """Test the concept parsing methods of post_workflow_results."""
        result_format = CONCEPTS

        message = Parse(
            load_fixture("clarifai/response_success.json"),
            service_pb2.PostWorkflowResultsResponse(),
        )

        self.api.stub.PostWorkflowResults.return_value = message

        result = self.api.post_workflow_results(
            "12345678abcdef", "General", result_format, b"Test"
        )

        concept_name = "dog"
        concept_value = 0.9979874

        assert CONCEPTS in result
        concepts = result[CONCEPTS]
        assert concept_name in concepts
        assert max(concepts[concept_name]) == pytest.approx(concept_value)

    def test_post_workflow_results_nested_concepts(self):
        """Test the recursive parser for collecting nested concepts."""
        result_format = CONCEPTS

        message = Parse(
            load_fixture("clarifai/response_nested_concepts.json"),
            service_pb2.PostWorkflowResultsResponse(),
        )

        self.api.stub.PostWorkflowResults.return_value = message

        result = self.api.post_workflow_results(
            "12345678abcdef", "General", result_format, b"Test"
        )

        concept_name = "Foo"
        concept_value = 0.9753649

        assert CONCEPTS in result
        concepts = result[CONCEPTS]
        assert concept_name in concepts
        assert max(concepts[concept_name]) == pytest.approx(concept_value)

    def test_post_workflow_results_response_failure(self):
        """Test a failed response from post_workflow_results."""
        message = Parse(
            load_fixture("clarifai/response_failure.json"),
            service_pb2.PostWorkflowResultsResponse(),
        )

        self.api.stub.PostWorkflowResults.return_value = message

        with pytest.raises(HomeAssistantError):
            self.api.post_workflow_results(
                "12345678abcdef", "General", "default", b"Test"
            )

    def test_post_workflow_results_invalid_result_format(self):
        """Test an invalid result_format."""
        result_format = "invalid"

        message = Parse(
            load_fixture("clarifai/response_success.json"),
            service_pb2.PostWorkflowResultsResponse(),
        )

        self.api.stub.PostWorkflowResults.return_value = message

        with pytest.raises(HomeAssistantError):
            self.api.post_workflow_results(
                "12345678abcdef", "General", result_format, b"Test"
            )
