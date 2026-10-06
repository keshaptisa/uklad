"""Шаг 1. Панель: расходы СберИндекса + справочник МО + Росстат + доступность рынков → data/processed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uklad.sources import build  # noqa: E402

spend, mo = build()
print(f"МО с полной историей: {spend.territory_id.nunique()}, месяцев: {spend.month.nunique()}")
print("Покрытие контекста (доля МО):")
print(mo.notna().mean().round(3).to_string())
