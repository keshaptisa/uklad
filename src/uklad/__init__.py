"""uklad — типы локальных экономик МО России по данным СберИндекса и Росстата."""
import sys
from pathlib import Path

import yaml

# консоль Windows по умолчанию в cp1251: печать кириллицы и символов вроде «→» падает
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure") and (_s.encoding or "").lower() != "utf-8":
        _s.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]


def load_config(name: str = "pipeline.yaml") -> dict:
    with open(ROOT / "configs" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)
