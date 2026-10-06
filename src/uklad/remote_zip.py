"""Чтение отдельных файлов из большого zip-архива по HTTP Range, без скачивания архива целиком.

Архивы Росстата в каталоге tochno.st весят гигабайты, а нужно из них несколько csv.
Оглавление zip (central directory) лежит в конце файла: читаем хвост, из него — каталог,
затем только нужные записи. Формат — спецификация PKWARE APPNOTE.TXT.
"""
from __future__ import annotations

import struct
import time
import urllib.request
import zlib


def _get(url: str, start: int, end: int, tries: int = 6) -> bytes:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def _size(url: str, tries: int = 6) -> int:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=60) as r:
                return int(r.headers["Content-Length"])
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("unreachable")


def list_entries(url: str) -> list[dict]:
    """Оглавление архива: имя, метод сжатия, размеры, смещение локального заголовка."""
    n = _size(url)
    tail = _get(url, max(0, n - 65_557), n - 1)
    i64 = tail.rfind(b"PK\x06\x07")  # указатель на ZIP64-конец каталога
    if i64 >= 0:
        off = struct.unpack("<Q", tail[i64 + 8:i64 + 16])[0]
        eocd = _get(url, off, off + 55)
        cd_size, cd_off = struct.unpack("<QQ", eocd[40:56])
    else:
        i = tail.rfind(b"PK\x05\x06")
        cd_size, cd_off = struct.unpack("<II", tail[i + 12:i + 20])
    cd = _get(url, cd_off, cd_off + cd_size - 1)
    out, p = [], 0
    while cd[p:p + 4] == b"PK\x01\x02":
        method = struct.unpack("<H", cd[p + 10:p + 12])[0]
        csize, usize = struct.unpack("<II", cd[p + 20:p + 28])
        nlen, elen, clen = struct.unpack("<HHH", cd[p + 28:p + 34])
        lho = struct.unpack("<I", cd[p + 42:p + 46])[0]
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen:p + 46 + nlen + elen]
        # ZIP64: настоящие размеры и смещение лежат в extra-поле 0x0001
        q = 0
        while q + 4 <= len(extra):
            tag, sz = struct.unpack("<HH", extra[q:q + 4])
            if tag == 1:
                vals, r = [], q + 4
                for flag in (usize, csize, lho):
                    if flag == 0xFFFFFFFF:
                        vals.append(struct.unpack("<Q", extra[r:r + 8])[0]); r += 8
                    else:
                        vals.append(flag)
                usize, csize, lho = vals
            q += 4 + sz
        out.append(dict(name=name, method=method, csize=csize, usize=usize, offset=lho))
        p += 46 + nlen + elen + clen
    return out


def read_entry(url: str, entry: dict) -> bytes:
    """Скачивает и распаковывает одну запись архива."""
    head = _get(url, entry["offset"], entry["offset"] + 29)
    nlen, elen = struct.unpack("<HH", head[26:30])
    start = entry["offset"] + 30 + nlen + elen
    raw = b"".join(
        _get(url, a, min(a + 64 * 2**20, start + entry["csize"]) - 1)
        for a in range(start, start + entry["csize"], 64 * 2**20)
    )
    if entry["method"] == 0:
        return raw
    if entry["method"] == 8:
        return zlib.decompress(raw, -15)
    raise ValueError(f"метод сжатия {entry['method']} не поддержан")
