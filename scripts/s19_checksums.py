"""Шаг 9. Контрольные суммы результатов: python scripts/s19_checksums.py [--check].

Без флага — записывает SHA-256 каждого файла outputs/ в outputs/CHECKSUMS.sha256.
С --check — сверяет текущие файлы с записанными суммами и печатает расхождения: так проверяется,
что прогон `run.py` на другой машине повторил результаты байт в байт (seed и версии пакетов закреплены).
Переводы строк приводятся к LF, чтобы Windows и Linux давали одинаковые суммы.
"""
import argparse
import hashlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
LIST = OUT / "CHECKSUMS.sha256"


def digest(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix in {".csv", ".json", ".txt", ".md"}:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


files = sorted(p for p in OUT.rglob("*") if p.is_file() and p != LIST)
cur = {p.relative_to(ROOT).as_posix(): digest(p) for p in files}

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
if not ap.parse_args().check:
    LIST.write_text("".join(f"{h}  {f}\n" for f, h in cur.items()), encoding="utf-8")
    print(f"{LIST.relative_to(ROOT).as_posix()}: {len(cur)} файлов")
    sys.exit(0)

ref = dict(reversed(line.split("  ", 1)) for line in LIST.read_text(encoding="utf-8").splitlines() if line)
diff = [f for f in ref if cur.get(f) != ref[f]]
new = [f for f in cur if f not in ref]
for f in diff:
    print(("ИЗМЕНЁН " if f in cur else "НЕТ     ") + f)
for f in new:
    print("НОВЫЙ   " + f)
print(f"совпали {len(ref) - len(diff)} из {len(ref)}")
sys.exit(1 if diff else 0)
