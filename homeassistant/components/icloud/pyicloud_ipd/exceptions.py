
from typing import Optional


class PyiCloudException(Exception):
    """Generic iCloud exception."""
    pass


#API
class PyiCloudAPIResponseException(PyiCloudException):
    """iCloud response exception."""
    def __init__(self, reason:str, code:Optional[str]=None, retry:bool=False):
        self.reason = reason
        self.code = code
        message = reason or ""
        if code:
            message += " (%s)" % code
        if retry:
            message += ". Retrying ..."

        super().__init__(message)


class PyiCloudServiceNotActivatedException(PyiCloudAPIResponseException):
    """iCloud service not activated exception."""
    pass


# Login
class PyiCloudFailedLoginException(PyiCloudException):
    """iCloud failed login exception."""
    pass


class PyiCloud2SARequiredException(PyiCloudException):
    """iCloud 2SA required exception."""
    def __init__(self, apple_id: str):
        message = "Two-step authentication required for account: %s" % apple_id
        super().__init__(message)


class PyiCloudNoStoredPasswordAvailableException(PyiCloudException):
    """iCloud no stored password exception."""
    pass


# Webservice specific
class PyiCloudNoDevicesException(PyiCloudException):
    """iCloud no device exception."""
    pass

# Potentially Deprecated - Further review needed
class PyiCloudConnectionException(PyiCloudException):
    pass


class PyiCloudAPIResponseError(PyiCloudException):
    def __init__(self, reason:str, code:(Optional[int])):
        self.reason = reason
        self.code = code
        message = reason
        if code:
            message += " (%s)" % code

        super(PyiCloudAPIResponseError, self).__init__(message)


class PyiCloud2SARequiredError(PyiCloudException):
    def __init__(self, url: str):
        message = "Two-step authentication required for %s" % url
        super(PyiCloud2SARequiredError, self).__init__(message)


class NoStoredPasswordAvailable(PyiCloudException):
    pass


class PyiCloudServiceNotActivatedErrror(PyiCloudAPIResponseError):
    pass
