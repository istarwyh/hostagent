# Run checks from the monorepo backend.
.PHONY: test lint typecheck
test:
	cd backend && .venv/bin/python -m pytest src/test/test_api_errors.py src/test/test_logging_system.py src/test/test_v1_migration.py src/test/test_audit_middleware.py
lint:
	cd backend && .venv/bin/python -m compileall -q src
typecheck:
	cd frontend && yarn tsc --noEmit
