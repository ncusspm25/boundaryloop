class BoundaryError(Exception):
    """A user-actionable failure; no traceback required at the CLI boundary."""


class SecurityError(BoundaryError):
    pass


class StateError(BoundaryError):
    pass


class ProviderError(BoundaryError):
    pass
