"""Constants for the Amazon Bedrock Agent integration test."""

import datetime
from typing import Final

CONST_PROMPT: Final = "Hello there."
CONST_ANSWER: Final = "General Kenobi."
CONST_PROMPT_CONTEXT: Final = "Provide a short answer to: "

CONST_DEFAULT_ANSWER: Final = "\nHow can I help you today?"

CONST_LIST_MODEL_RESPONSE: Final = {
    "ResponseMetadata": {
        "RequestId": "61519929-81d2-415f-82be-bf4598ae37a0",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {},
        "RetryAttempts": 0,
    },
    "modelSummaries": [
        {
            "modelArn": "arn:aws:bedrock:us-west-2::foundation-model/amazon.titan-tg1-large",
            "modelId": "amazon.titan-tg1-large",
            "modelName": "Titan Text Large",
            "providerName": "Amazon",
            "inputModalities": ["TEXT"],
            "outputModalities": ["TEXT"],
            "responseStreamingSupported": True,
            "customizationsSupported": [],
            "inferenceTypesSupported": ["ON_DEMAND"],
            "modelLifecycle": {"status": "ACTIVE"},
        }
    ],
}

CONST_CONVERSE_RESPONSE: Final = {
    "ResponseMetadata": {
        "RequestId": "474ef87b-6736-4cdc-ba44-1d1cd3172006",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "date": "Sat, 08 Jun 2024 04:55:18 GMT",
            "content-type": "application/json",
            "content-length": "206",
            "connection": "keep-alive",
            "x-amzn-requestid": "474ef87b-6736-4cdc-ba44-1d1cd3172006",
        },
        "RetryAttempts": 0,
    },
    "output": {
        "message": {
            "role": "assistant",
            "content": [{"text": "\nHow can I help you today?"}],
        }
    },
    "stopReason": "end_turn",
    "usage": {"inputTokens": 8, "outputTokens": 6, "totalTokens": 14},
    "metrics": {"latencyMs": 354},
}


CONST_LIST_KNOWLEDGEBASE_RESPONSE: Final = {
    "ResponseMetadata": {
        "RequestId": "402bd2d5-5ac1-4143-af1c-f03b104c5ae9",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {...},
        "RetryAttempts": 0,
    },
    "knowledgeBaseSummaries": [
        {
            "knowledgeBaseId": "123",
            "name": "knowledge-test",
            "description": "testing content ingestion from website",
            "status": "ACTIVE",
            "updatedAt": datetime.datetime(2024, 4, 20, 22, 50, 54, 262369),
        }
    ],
}

CONST_KNOWLEDGEBASE_RESPONSE: Final = {
    "ResponseMetadata": {
        "RequestId": "ba0a7935-dd93-432d-9f7a-a49af092dcd8",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "date": "Wed, 17 Apr 2024 12:32:59 GMT",
            "content-type": "application/json",
            "content-length": "301",
            "connection": "keep-alive",
            "x-amzn-requestid": "ba0a7935-dd93-432d-9f7a-a49af092dcd8",
        },
        "RetryAttempts": 0,
    },
    "sessionId": "844528b9-bcae-4c9f-8c21-a4e04cb520b8",
    "output": {"text": "Sorry, I am unable to assist you with this request."},
    "citations": [
        {
            "generatedResponsePart": {
                "textResponsePart": {
                    "text": "Sorry, I am unable to assist you with this request.",
                    "span": {},
                }
            },
            "retrievedReferences": [],
        }
    ],
}
