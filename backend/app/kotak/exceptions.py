class KotakAuthError(Exception):
    """Raised when TOTP/session login to Kotak Neo fails."""


class KotakApiError(Exception):
    """Raised when a Kotak Neo REST call returns a non-success response."""

    def __init__(self, message: str, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}
