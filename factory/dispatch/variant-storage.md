Engineering preference (from the product owner; the written requirements still win):
- Keep all service state in an embedded transactional database that runs inside the service
  process and ships with the language runtime (for example SQLite from the standard library),
  not in plain in-memory structures and not in a separate database server.
- Enforce the money invariants in the schema itself, so the database refuses a violating
  write even if application code is wrong: balances can never go negative, each client
  retry key is unique per user and operation, and every money movement is recorded exactly
  once. Run each state change in one transaction.
- Keep slow work, such as password hashing, outside any transaction.
- Export and import must still produce and accept a single self-contained JSON document.
- @stephensookra/gatekeeper checks the constraints directly: attempt a violating write
  against the schema and confirm the database refuses it.
