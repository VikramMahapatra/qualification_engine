from __future__ import annotations


class EngineError(Exception):
    """Base error for the qualification engine."""

    status_code = 500
    code = "engine_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(EngineError):
    status_code = 404
    code = "not_found"


class ConflictError(EngineError):
    status_code = 409
    code = "conflict"


class ValidationError(EngineError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(EngineError):
    status_code = 401
    code = "unauthenticated"


class AuthorizationError(EngineError):
    status_code = 403
    code = "forbidden"
