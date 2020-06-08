"""Constants for the Clarifai integration."""

DOMAIN = "clarifai"

CONF_APP_ID = ATTR_APP_ID = "app_id"
CONF_WORKFLOW_ID = ATTR_WORKFLOW_ID = "workflow_id"
CONF_RESULT_FORMAT = ATTR_RESULT_FORMAT = "result_format"

SERVICE_PREDICT = "predict"
EVENT_PREDICTION = f"{DOMAIN}.prediction"

WORKFLOW_ERROR = "Can't process image using %s workflow with error: %s"

OUTPUTS = "outputs"
CONCEPTS = "concepts"
DEFAULT = "default"
