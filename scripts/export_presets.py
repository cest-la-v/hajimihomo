#!/usr/bin/env python3
"""Output profiles/presets/*.yaml as a single JSON object to stdout."""
import json
import sys
from pathlib import Path

import yaml

presets_dir = Path(__file__).parent.parent / "profiles" / "presets"
presets = {}
for path in sorted(presets_dir.glob("*.yaml")):
    data = yaml.safe_load(path.read_text()) or {}
    name = data.get("name") or path.stem
    presets[name] = {
        "description": data.get("description", ""),
        "groups": data.get("groups", []),
    }

json.dump(presets, sys.stdout, ensure_ascii=False, indent=2)
