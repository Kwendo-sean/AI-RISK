"""Regenerate the versioned admin-friendly career seed from the legacy adapter.

Run only when deliberately publishing a new content version. Runtime reads the
committed JSON seed and does not require this script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
import platform_content


target = Path(__file__).parents[1] / "content" / "careers.v1.json"
payload = {"dataset_version": platform_content.DATASET_VERSION, "careers": list(platform_content.build_career_seed())}
target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {len(payload['careers'])} careers to {target}")
