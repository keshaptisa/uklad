"""Шаг 0. Скачивание исходных данных в data/raw с проверкой контрольных сумм.

Источники:
- СберИндекс, архив хакатона (расходы по МО, доступность рынков, связи МО) — sberbank.com;
- СберИндекс, справочник и границы МО (rar) — sberbank.com;
- СберИндекс, API дашбордов: индекс мобильности и расходы по МО (`/api/dataset/v1/download/{slug}/parquet`);
- Росстат, БД показателей МО через каталог «Если быть точным» — нужные csv читаются из многогигабайтных zip по HTTP Range.

Сайты Сбера используют сертификат Национального удостоверяющего центра (Минцифры), которого нет в стандартных
хранилищах, поэтому проверка TLS для них отключена. Подлинность файлов вместо этого проверяется по SHA-256:
при несовпадении скрипт останавливается (для данных API, которые обновляются, — только предупреждает).
"""
import hashlib
import shutil
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uklad.remote_zip import list_entries, read_entry  # noqa: E402

RAW = ROOT / "data" / "raw"
SBER = {
    "hackathon.zip": ("https://www.sberbank.com/common/img/uploaded/files/pdf/sberindex/hackathonlicence.zip",
                      "a9f932ff4096a7df797d1547987937f34d3995ac445b4748177114488d12b010", True),
    "t_dict_municipal.rar": ("https://www.sberbank.com/common/files/t_dict_municipal.rar",
                             "319ed22684b77716641bc15b61f7325adc44e9fc47e9be2973d88412d27d21f5", True),
    "indeks-mobilnosti.parquet": ("https://sberindex.ru/api/dataset/v1/download/indeks-mobilnosti/parquet",
                                  "f16f7d8088c7d0a02ea770915c512343807e65fc5bcc177af3bd64512add5708", False),
}
ROSSTAT_URL = ("https://storage.yandexcloud.net/tochno-st-catalog/Rosstat/data_bdmo_118_v20250918/by_indicator/"
               "data_section{}_112_v20250918.zip")
ROSSTAT = {  # (раздел, показатель, год): sha256
    (31, "Y48112027", 2023): "5941ec6ffba6b0b28c0b7fea6febe357e961787f69fba457babca1496196478e",
    (31, "Y48112027", 2024): "51c0f94db92e3b7e16b145b67c78fc1ee0367bd1b84a144711dbc2a899d688fc",
    (32, "Y48423005", 2023): "e2cc8f029abd940fc301ea6f13e1c565fdd08803d626cc8e3836b3fe64858e42",
    (32, "Y48423005", 2024): "cdde683ec93bd434554ad6f6c09ab13a155e5b56c74a38fd7c9d7d92670567af",
    (32, "Y48423007", 2023): "23c8c6635e6d7d7d2e34ef6894c0ad9f56648b2436f61802a9842c4ee080a86c",
    (32, "Y48423007", 2024): "78477a030f2bc4d17d0152eaf25b9c4bcd8decabe0252154d12a3306d0d4f922",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check(p: Path, expected: str, strict: bool):
    got = sha(p)
    if got == expected:
        print("  sha256 ok")
    elif strict:
        sys.exit(f"  sha256 НЕ СОВПАЛ для {p.name}: {got} — файл изменён или повреждён")
    else:
        print(f"  внимание: sha256 {p.name} изменился (данные API обновляются): {got}")


def fetch(url: str, dest: Path):
    ctx = ssl._create_unverified_context()  # см. docstring: подлинность — по SHA-256
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=300) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def extract(archive: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for cmd in (["7z", "x", "-y", f"-o{dest}", str(archive)], ["tar", "-xf", str(archive), "-C", str(dest)]):
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    sys.exit(f"не удалось распаковать {archive}: нужен 7z или bsdtar (в Windows 10+ — штатный tar.exe)")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (url, h, strict) in SBER.items():
        p = RAW / name
        if not p.exists():
            print("скачиваю", name)
            fetch(url, p)
        print(name)
        check(p, h, strict)
    if not (RAW / "hackathonlicence" / "consumption.parquet").exists():
        extract(RAW / "hackathon.zip", RAW)
    if not (RAW / "dict" / "t_dict_municipal_districts.xlsx").exists():
        extract(RAW / "t_dict_municipal.rar", RAW / "dict")

    (RAW / "rosstat").mkdir(exist_ok=True)
    entries = {}
    for (sec, code, year), h in ROSSTAT.items():
        p = RAW / "rosstat" / f"{code}_{year}.csv"
        if not p.exists():
            url = ROSSTAT_URL.format(sec)
            entries.setdefault(sec, list_entries(url))
            e = [x for x in entries[sec] if x["name"].endswith(f"data_{code}_year{year}_112_v20250918.csv")]
            print("Росстат: извлекаю", p.name)
            p.write_bytes(read_entry(url, e[0]))
        print(p.name)
        check(p, h, True)
    print("готово")


if __name__ == "__main__":
    main()
