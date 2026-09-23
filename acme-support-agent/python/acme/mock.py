import os
def mock_enabled() -> bool:
    return os.environ.get("ACME_MOCK", "").lower() in ("1", "true", "yes")
