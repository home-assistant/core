"""Constants for tests of the SMS component."""

import datetime

SMS_STATUS_SINGLE = {
    "SIMUnRead": 0,
    "SIMUsed": 1,
    "SIMSize": 30,
    "PhoneUnRead": 0,
    "PhoneUsed": 0,
    "PhoneSize": 50,
    "TemplatesUsed": 0,
}

NEXT_SMS_SINGLE = [
    {
        "SMSC": {
            "Location": 0,
            "Name": "",
            "Format": "Text",
            "Validity": "NA",
            "Number": "+358444111111",
            "DefaultNumber": "",
        },
        "UDH": {
            "Type": "NoUDH",
            "Text": b"",
            "ID8bit": 0,
            "ID16bit": 0,
            "PartNumber": -1,
            "AllParts": 0,
        },
        "Folder": 1,
        "InboxFolder": 1,
        "Memory": "SM",
        "Location": 1,
        "Name": "",
        "Number": "+358444222222",
        "Text": "Short message",
        "Type": "Deliver",
        "Coding": "Default_No_Compression",
        "DateTime": datetime.datetime(2024, 3, 23, 20, 15, 37),
        "SMSCDateTime": datetime.datetime(2024, 3, 23, 20, 15, 41),
        "DeliveryStatus": 0,
        "ReplyViaSameSMSC": 0,
        "State": "UnRead",
        "Class": -1,
        "MessageReference": 0,
        "ReplaceMessage": 0,
        "RejectDuplicates": 0,
        "Length": 7,
    }
]

SMS_STATUS_MULTIPLE = {
    "SIMUnRead": 0,
    "SIMUsed": 2,
    "SIMSize": 30,
    "PhoneUnRead": 0,
    "PhoneUsed": 0,
    "PhoneSize": 50,
    "TemplatesUsed": 0,
}

NEXT_SMS_MULTIPLE_1 = [
    {
        "SMSC": {
            "Location": 0,
            "Name": "",
            "Format": "Text",
            "Validity": "NA",
            "Number": "+358444111111",
            "DefaultNumber": "",
        },
        "UDH": {
            "Type": "ConcatenatedMessages",
            "Text": b"\x05\x00\x03\x00\x02\x01",
            "ID8bit": 0,
            "ID16bit": -1,
            "PartNumber": 1,
            "AllParts": 2,
        },
        "Folder": 1,
        "InboxFolder": 1,
        "Memory": "SM",
        "Location": 1,
        "Name": "",
        "Number": "+358444222222",
        "Text": "Longer test again: 01234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123",
        "Type": "Deliver",
        "Coding": "Default_No_Compression",
        "DateTime": datetime.datetime(2024, 3, 25, 19, 53, 56),
        "SMSCDateTime": datetime.datetime(2024, 3, 25, 19, 54, 6),
        "DeliveryStatus": 0,
        "ReplyViaSameSMSC": 0,
        "State": "UnRead",
        "Class": -1,
        "MessageReference": 0,
        "ReplaceMessage": 0,
        "RejectDuplicates": 0,
        "Length": 153,
    }
]

NEXT_SMS_MULTIPLE_2 = [
    {
        "SMSC": {
            "Location": 0,
            "Name": "",
            "Format": "Text",
            "Validity": "NA",
            "Number": "+358444111111",
            "DefaultNumber": "",
        },
        "UDH": {
            "Type": "ConcatenatedMessages",
            "Text": b"\x05\x00\x03\x00\x02\x02",
            "ID8bit": 0,
            "ID16bit": -1,
            "PartNumber": 2,
            "AllParts": 2,
        },
        "Folder": 1,
        "InboxFolder": 1,
        "Memory": "SM",
        "Location": 2,
        "Name": "",
        "Number": "+358444222222",
        "Text": "4567890123456789012345678901",
        "Type": "Deliver",
        "Coding": "Default_No_Compression",
        "DateTime": datetime.datetime(2024, 3, 25, 19, 53, 56),
        "SMSCDateTime": datetime.datetime(2024, 3, 25, 19, 54, 7),
        "DeliveryStatus": 0,
        "ReplyViaSameSMSC": 0,
        "State": "UnRead",
        "Class": -1,
        "MessageReference": 0,
        "ReplaceMessage": 0,
        "RejectDuplicates": 0,
        "Length": 28,
    }
]
