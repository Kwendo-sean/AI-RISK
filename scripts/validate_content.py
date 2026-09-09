"""Validate career, question, and skill coverage; exits non-zero on errors."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from platform_content import validate_content

report = validate_content()
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["valid"] else 1)
