"""Скачивает сторонний код без лицензии на закреплённом коммите в third_party/ (в репозиторий не входит).

CANUS (Shalileh, IEEE Access 2025) — метод члена жюри; у репозитория нет файла LICENSE, поэтому код не копируем,
а клонируем при запуске. Без него сравнение методов просто пропускает CANUS.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOS = {"CANUS": ("https://github.com/Sorooshi/CANUS.git", "754622af6eff9604a590e862a108c4c4212acf2d")}

for name, (url, commit) in REPOS.items():
    dest = ROOT / "third_party" / name
    if not dest.exists():
        subprocess.run(["git", "clone", "-q", url, str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", commit], check=True)
    print(name, "->", dest, "@", commit[:7])
