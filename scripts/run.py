"""Весь пайплайн одной командой: python scripts/run.py [--skip-download] [--from ШАГ].

Шаги идут по порядку; каждый пишет свои результаты в outputs/<шаг>/ (см. README).
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("s01_download", "скачивание данных с проверкой SHA-256"),
    ("s02_panel", "панель: расходы + справочник + Росстат"),
    ("s03_edges", "восемь правил ребра (включая слияние SNF) и их сравнение"),
    ("s04_external_code", "код CANUS (Shalileh, 2025) на закреплённом коммите"),
    ("s05_choose_k", "выбор числа типов по устойчивости"),
    ("s06_methods", "13 методов по ICVI: рейтинг выбора и контрольная группа"),
    ("s07_edge_effect", "влияние правила ребра на типологию"),
    ("s08_dynamics", "24 помесячные сети и отслеживание типов"),
    ("s09_synthetic", "проверка отслеживания типов на синтетике"),
    ("s10_rhythm", "линза ритма"),
    ("s11_types", "профили, FCA, OIPC, внешняя проверка"),
    ("s12_transitions", "направленные и возвратные переходы"),
    ("s23_validation", "проверка на отложенных признаках и значимость переходов"),
    ("s13_checks", "устойчивость рейтинга (Борда, Коупленд, BasicMQ, внешняя ж/д сеть), отпечатки типов, разрыв между типами"),
    ("s14_network_layout", "раскладка сети МО для лендинга и статистика рёбер"),
    ("s15_geo", "границы МО для карты"),
    ("s16_figures", "рисунки отчёта"),
    ("s17_site_data", "данные лендинга"),
    ("s18_site", "сборка лендинга site/index.html"),
    ("report", "методологический отчёт report/uklad_methodology.{md,pdf} и приложения"),
    ("s22_slides", "презентация docs/uklad_slides.pdf"),
    ("s19_checksums", "контрольные суммы результатов (проверка повторяемости)"),
]

ap = argparse.ArgumentParser()
ap.add_argument("--skip-download", action="store_true")
ap.add_argument("--from", dest="start", default=None, help="начать с этого шага")
a = ap.parse_args()
names = [s for s, _ in STEPS]
start = names.index(a.start) if a.start else 0
for name, what in STEPS[start:]:
    if a.skip_download and name == "s01_download":
        continue
    print(f"\n=== {name}: {what}", flush=True)
    t = time.time()
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / f"{name}.py")], cwd=ROOT)
    if r.returncode:
        sys.exit(f"шаг {name} завершился с ошибкой {r.returncode}")
    print(f"--- {name}: {time.time() - t:.0f} с", flush=True)
