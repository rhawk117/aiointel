




class AioIntelHTTPError(Exception):
    """Base exception for aiointel HTTP errors."""


class URLPolicyError(AioIntelHTTPError):
    """Exception raised for URL policy violations."""

class NoAttemptsLeftError(AioIntelHTTPError):
    """Exception raised when no attempts are left for a request."""
    