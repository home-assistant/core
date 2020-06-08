"""Clarifai API for communication using gRPC client."""

import json

from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from google.protobuf import json_format

from homeassistant.exceptions import HomeAssistantError

from .const import CONCEPTS, DEFAULT, OUTPUTS


class Clarifai:
    """Clarifai API for Home Assistant."""

    def __init__(self, access_token):
        """Initialize Clarifai API."""
        self._access_token = access_token
        self._stub = service_pb2_grpc.V2Stub(ClarifaiChannel.get_json_channel())
        self._metadata = (("authorization", f"Key {access_token}"),)

    def list_apps(self):
        """List all applications available to user."""
        request = service_pb2.ListAppsRequest()
        response = self._stub.ListApps(request, metadata=self._metadata)
        if _validate_response(response):
            return {app.name: app.id for app in response.apps}

    def list_app_scopes(self, app_id):
        """List allowed scopes for configured access_token and application."""
        request = service_pb2.MyScopesRequest(
            user_app_id=resources_pb2.UserAppIDSet(app_id=app_id)
        )
        response = self._stub.MyScopes(request, metadata=self._metadata)
        if _validate_response(response):
            return response.scopes

    def post_workflow_results(self, app_id, workflow_id, result_format, image_bytes):
        """Run a workflow with a given image and return the results."""
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
        response = self._stub.PostWorkflowResults(request, metadata=self._metadata)
        if _validate_response(response):
            return _parse_workflow_response(response, result_format)


def _validate_response(response):
    """Validate that the response returned from a request was successful."""
    if response.status.code != status_code_pb2.SUCCESS:
        raise HomeAssistantError(
            f"Request failed, status code: {str(response.status.code)}"
        )
    return True


def _parse_workflow_response(response, result_format=DEFAULT):
    """Parse a response containing a WorkflowResult object."""
    workflow_result = response.results[0]  # we send 1 input so we get 1 result

    if result_format == DEFAULT:
        return _parse_default(workflow_result)
    if result_format == CONCEPTS:
        return _parse_concepts(workflow_result)

    raise HomeAssistantError(f"Invalid workflow result format: {result_format}")


def _parse_default(workflow_result):
    """Parse a WorkflowResult object and return outputs in their default format from Clarifai."""
    return {OUTPUTS: json.loads(json_format.MessageToJson(workflow_result))[OUTPUTS]}


def _parse_concepts(workflow_result):
    """Parse concepts from a WorkflowResult object.

    Parse a WorkflowResult, flattening concepts into a dictionary with
    the name of the concept as the key and a list of confidence values
    as a value.

    Ex:
    "concepts": {
        "concept1": [
            0.98727286
        ],
        "concept2": [
            0.9732269
        ]
    }
    """
    concepts = {}
    for output in workflow_result.outputs:
        _parse_recursively(concepts, output.data)
    return {CONCEPTS: concepts}


def _parse_recursively(concepts, output_data):
    """Recursively parse through the output data of a model for concepts."""
    for concept in output_data.concepts:
        if concept.value > 0:
            if concept.name not in concepts:
                concepts[concept.name] = []
            concepts[concept.name].append(concept.value)

    for region in output_data.regions:
        _parse_recursively(concepts, region.data)
