from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    code = "domain_error"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class AuthorizationError(DomainError):
    status_code = 403
    code = "forbidden"


class InvalidStateError(DomainError):
    status_code = 409
    code = "invalid_state"


class PolicyViolationError(DomainError):
    status_code = 403
    code = "policy_violation"


class ToolTimeoutAfterSuccess(RuntimeError):
    """The remote tool committed the requested write but its response was lost."""
