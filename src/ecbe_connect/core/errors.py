class ECBEConnectError(Exception):
    """Base exception safe to present to a user."""


class ValidationError(ECBEConnectError):
    pass


class AuthenticationFailed(ECBEConnectError):
    pass


class UserCancelled(ECBEConnectError):
    pass


class HostKeyUnknown(ECBEConnectError):
    pass


class HostKeyChanged(ECBEConnectError):
    pass


class RemoteOutputError(ECBEConnectError):
    pass


class ViewerNotFound(ECBEConnectError):
    pass


class CredentialStoreUnavailable(ECBEConnectError):
    pass


class ConnectionAlreadyActive(ECBEConnectError):
    pass

