#!/usr/bin/env python3
# ══════════════════════════════════════════════════
# 🔤 glyph-check — есть ли глиф в шрифте на самом деле
# ══════════════════════════════════════════════════
# Отсутствующий глиф рисуется «тофу» — пустым прямоугольником,
# и увидеть это в тексте нельзя: в выводе он выглядит обычным
# одиночным символом. Nerd Fonts v3 переставила многие позиции
# PUA, поэтому шпаргалки старше v3 врут.
#
#   python3 scripts/glyph-check.py shell/eza/cameo-dark/theme.yml
#   python3 scripts/glyph-check.py --font ~/Library/Fonts/X.ttf FILE...
#
# Читает cmap напрямую (форматы 4 и 12). fontTools не нужен.

import argparse
import re
import struct
import sys
from pathlib import Path

DEFAULT_FONT = Path.home() / "Library/Fonts/MapleMono-NF-Regular.ttf"


def cmap_codepoints(path):
    d = Path(path).read_bytes()
    num_tables = struct.unpack(">H", d[4:6])[0]
    cmap_off = None
    for i in range(num_tables):
        rec = 12 + i * 16
        if d[rec:rec + 4] == b"cmap":
            cmap_off = struct.unpack(">I", d[rec + 8:rec + 12])[0]
            break
    if cmap_off is None:
        sys.exit("❌ в шрифте нет таблицы cmap")

    n = struct.unpack(">H", d[cmap_off + 2:cmap_off + 4])[0]
    best, best_score = None, -1
    for i in range(n):
        rec = cmap_off + 4 + i * 8
        pid, eid, off = struct.unpack(">HHI", d[rec:rec + 8])
        sub = cmap_off + off
        fmt = struct.unpack(">H", d[sub:sub + 2])[0]
        # предпочитаем format 12 (полный Unicode), затем format 4
        score = {12: 3, 4: 2}.get(fmt, 0) + (1 if (pid, eid) in ((3, 10), (3, 1), (0, 4), (0, 3)) else 0)
        if score > best_score:
            best, best_score = (sub, fmt), score
    sub, fmt = best
    cps = set()

    if fmt == 12:
        ngroups = struct.unpack(">I", d[sub + 12:sub + 16])[0]
        for g in range(ngroups):
            o = sub + 16 + g * 12
            start, end, _ = struct.unpack(">III", d[o:o + 12])
            if end - start > 0x20000:      # защита от мусора
                continue
            cps.update(range(start, end + 1))
    elif fmt == 4:
        segx2 = struct.unpack(">H", d[sub + 6:sub + 8])[0]
        seg = segx2 // 2
        ends = struct.unpack(f">{seg}H", d[sub + 14:sub + 14 + segx2])
        starts_off = sub + 16 + segx2
        starts = struct.unpack(f">{seg}H", d[starts_off:starts_off + segx2])
        for s, e in zip(starts, ends):
            if s == 0xFFFF:
                continue
            cps.update(range(s, e + 1))
    else:
        sys.exit(f"❌ неподдерживаемый формат cmap: {fmt}")
    return cps, fmt


def main():
    ap = argparse.ArgumentParser(description="Проверить, что глифы реально есть в шрифте")
    ap.add_argument("files", nargs="+", help="файлы, из которых вынимать глифы")
    ap.add_argument("--font", default=str(DEFAULT_FONT))
    a = ap.parse_args()

    if not Path(a.font).exists():
        sys.exit(f"❌ шрифт не найден: {a.font}")
    cps, fmt = cmap_codepoints(a.font)
    print(f"  шрифт: {Path(a.font).name} — cmap format {fmt}, {len(cps)} кодпоинтов")

    bad = 0
    seen = {}
    for f in a.files:
        text = Path(f).read_text()
        # glyph: "X" из theme.yml
        for m in re.finditer(r'glyph:\s*"([^"]*)"', text):
            g = m.group(1)
            label = f"{Path(f).name}"
            if len(g) != 1:
                print(f"  ❌ {label}: глиф длиной {len(g)} — уронит ВЕСЬ файл (нужен ровно 1 символ)")
                bad += 1
                continue
            cp = ord(g)
            if cp not in cps:
                print(f"  ❌ {label}: U+{cp:04X} ОТСУТСТВУЕТ в шрифте — отрисуется тофу")
                bad += 1
            seen.setdefault(cp, 0)
            seen[cp] += 1

    dup = {cp: n for cp, n in seen.items() if n > 1}
    if dup:
        print(f"  ⚠️  повторяющиеся глифы ({len(dup)}): " +
              ", ".join(f"U+{cp:04X}×{n}" for cp, n in sorted(dup.items())[:8]))
    print(f"  проверено глифов: {sum(seen.values())}, уникальных: {len(seen)}")
    if bad:
        print(f"\n  ❌ провал: {bad}")
        sys.exit(1)
    print("\n  ✅ все глифы есть в шрифте")


if __name__ == "__main__":
    main()
