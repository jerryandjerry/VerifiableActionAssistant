# Security policy

This repository is a teaching reference, not a claim of prompt-injection immunity.

Do not include real secrets or customer data in issues. Report security findings privately
to the repository owner. The default demo uses fake tenants, fake documents, and a
SQLite-backed Jira simulator.

The system treats retrieved content as untrusted data, validates access in application code,
requires approval before writes, uses idempotency keys for side effects, and records an audit
trail. Those controls reduce risk but do not replace a full production review.
