#!/usr/bin/env python3
"""Build Cameo's Zed theme, with optional web token exports."""
import argparse
import json
import re
import sys
import tomllib
from pathlib import Path


def load_toml(path):
    with Path(path).open("rb") as stream:
        return tomllib.load(stream)


# ──────────────────────────────────────────────────
#  Цвет и WCAG
# ──────────────────────────────────────────────────
def rgb(hex_):
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_):
    r, g, b = rgb(hex_)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


ADVISORY = 4.5  # справочная планка «читаемый текст»


# ──────────────────────────────────────────────────
#  Палитра
# ──────────────────────────────────────────────────
class Palette:
    def __init__(self, path):
        self.path = Path(path)
        self.d = load_toml(path)
        self.meta = self.d["meta"]
        self.name = self.meta["name"]
        self._resolve_roles()

    def _resolve_roles(self):
        self.roles = {}
        raw = self.d["roles"]
        for key, spec in raw.items():
            src = spec
            if "same_as" in spec:                    # алиас: та же краска
                base = raw[spec["same_as"]]
                src = {**base, **{k: v for k, v in spec.items() if k != "same_as"}}
                src["hex"] = base["hex"]
            if "hex" not in src:
                die(f"role '{key}': нет hex и нет same_as")
            self.roles[key] = src

    def hex(self, role):
        if role not in self.roles:
            die(f"неизвестная роль '{role}' (есть: {', '.join(sorted(self.roles))})")
        return self.roles[role]["hex"]

    # ── WCAG-гейт ──
    def audit(self):
        rows, failures = [], []
        for key in sorted(self.roles):
            spec = self.roles[key]
            against = spec.get("on")
            if not against:
                rows.append((key, spec["hex"], "—", None, None, True))
                continue
            ratio = contrast(spec["hex"], self.hex(against))
            floor = float(spec.get("min", ADVISORY))
            ok = ratio + 1e-9 >= floor
            rows.append((key, spec["hex"], against, ratio, floor, ok))
            if not ok:
                failures.append(f"role {key} ({spec['hex']}) на {against}: {ratio:.2f} < min {floor}")
        pairs = []
        for p in self.d.get("pairs", []):
            ratio = contrast(self.hex(p["fg"]), self.hex(p["bg"]))
            floor = float(p.get("min", ADVISORY))
            ok = ratio + 1e-9 >= floor
            pairs.append((p.get("label", f"{p['fg']}/{p['bg']}"), p["fg"], p["bg"], ratio, floor, ok))
            if not ok:
                failures.append(f"pair {p.get('label')}: {p['fg']} на {p['bg']} = {ratio:.2f} < min {floor}")
        return rows, pairs, failures

    def report(self, out=sys.stdout):
        rows, pairs, failures = self.audit()
        w = out.write
        w(f"\n  WCAG-отчёт · {self.meta['label']} ({self.name}, {self.meta['mode']})\n")
        w(f"  {'роль':<10} {'hex':<9} {'на':<8} {'ratio':>6} {'min':>5}  gate  текст≥4.5\n")
        w("  " + "─" * 56 + "\n")
        for key, hx, against, ratio, floor, ok in rows:
            if ratio is None:
                w(f"  {key:<10} {hx:<9} {'—':<8} {'—':>6} {'—':>5}   —      —\n")
                continue
            adv = "✓" if ratio >= ADVISORY else "·"
            w(f"  {key:<10} {hx:<9} {against:<8} {ratio:>6.2f} {floor:>5.2f}  "
              f"{'PASS' if ok else 'FAIL'}    {adv}\n")
        w("\n  пары (текст на своей подложке)\n")
        w("  " + "─" * 56 + "\n")
        for label, fg, bg, ratio, floor, ok in pairs:
            w(f"  {label:<34} {ratio:>6.2f} {floor:>5.2f}  {'PASS' if ok else 'FAIL'}\n")
        if failures:
            w(f"\n  ❌ гейт не пройден — {len(failures)} нарушени(й):\n")
            for f in failures:
                w(f"     • {f}\n")
        else:
            w(f"\n  ✅ гейт пройден — {len(rows)} ролей, {len(pairs)} пар\n")
        return failures


def die(msg):
    sys.stderr.write(f"palette-build: ❌ {msg}\n")
    sys.exit(2)



def write_file(path, text, results, dry):
    path = Path(path)
    old = path.read_text(encoding="utf-8") if path.exists() else None
    state = "unchanged" if old == text else ("new" if old is None else "updated")
    if not dry and state != "unchanged":
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    results.append((state, str(path)))


# ──────────────────────────────────────────────────
#  Кросс-темные приёмники (CSS, JSON)
# ──────────────────────────────────────────────────
# Эти два файла описывают ПАРУ целиком, а не одну тему:
# CSS обязан держать светлую и тёмную в одном файле
# (контракт трёх состояний), JSON — обе палитры сразу.
# Поэтому пара собирается из вызванной палитры + её
# meta.twin, и результат байт в байт одинаков, с какой
# бы из двух палитр ни запустили сборку.

# Ключи [ghostty], которые описывают поверхности терминала,
# а не ANSI-рампу. Попадают в JSON как есть (в порядке этого
# кортежа — детерминированно, независимо от порядка в TOML).
SURFACE_KEYS = (
    "background", "foreground",
    "cursor-color", "cursor-text",
    "selection-background", "selection-foreground",
    "search-background", "search-foreground",
    "search-selected-background", "search-selected-foreground",
)


def family_of(a, b):
    """cameo-dark + cameo-light → cameo. Имя семейства = общий
    префикс пары. Отсюда берутся имена cameo.css / cameo.tokens.json
    и префикс CSS-переменных."""
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return a[:n].rstrip("-_") or a


def load_pair(p):
    """Возвращает (pair, problems). problems непустой → кросс-темные
    файлы НЕ пишутся, но остальная сборка идёт как обычно: тема,
    которую попросили собрать, гейт прошла, и её приёмники корректны.
    Ронять весь запуск из-за соседней палитры нельзя — это ровно тот
    случай, для которого в отчёте есть отдельная метка."""
    twin_name = p.meta.get("twin", p.name)
    if twin_name == p.name:
        return None, [f"{p.name}: meta.twin не задан — пары нет"]
    tpath = p.path.parent / f"{twin_name}.toml"
    if not tpath.exists():
        return None, [f"нет файла близнеца: {tpath}"]
    twin = Palette(tpath)
    # Близнец тоже уходит в CSS/JSON, поэтому его контраст тоже
    # проверяем — но отказом только от этих двух файлов.
    tfail = twin.audit()[2]
    if tfail:
        return None, [f"близнец {twin.name} не прошёл гейт:"] + [f"  • {f}" for f in tfail]
    by_mode = {}
    for q in (p, twin):
        by_mode.setdefault(q.meta["mode"], q)
    if set(by_mode) != {"light", "dark"}:
        return None, [f"пара {p.name}/{twin.name}: режимы {sorted(by_mode)}, "
                      f"нужны ровно light и dark"]
    light, dark = by_mode["light"], by_mode["dark"]
    if set(light.roles) != set(dark.roles):
        only_l = sorted(set(light.roles) - set(dark.roles))
        only_d = sorted(set(dark.roles) - set(light.roles))
        return None, [f"наборы ролей разошлись: только в {light.name}: {only_l or '—'}; "
                      f"только в {dark.name}: {only_d or '—'}"]
    ansi = {}
    for q, key in ((light, "light"), (dark, "dark")):
        ansi[key] = {int(e["i"]): e for e in q.d["ghostty"]["ansi"]}
    if sorted(ansi["light"]) != sorted(ansi["dark"]):
        return None, ["ANSI-слоты разошлись между темами"]
    return {"light": light, "dark": dark,
            "family": family_of(light.name, dark.name),
            # Порядок ролей — авторский, из светлого TOML. Один и тот
            # же в трёх CSS-блоках и в JSON, иначе файл перестал бы
            # быть байт-стабильным.
            "order": list(light.roles),
            "ansi": sorted(ansi["light"])}, []


def css_var(fam, role):
    return f"--{fam}-{role.replace('_', '-')}"


def pad_css(text, note, col=44):
    return text + " " * max(1, col - len(text)) + "/* " + note + " */"


def _css_tokens(p, pair, indent, notes):
    """42 объявления: 26 ролей + 16 ANSI. Одинаковый набор во всех
    трёх блоках — ни одна переменная не должна существовать только
    внутри media/[data-theme], иначе тема-по-умолчанию её потеряет."""
    fam, L = pair["family"], []
    for role in pair["order"]:
        decl = f'{indent}{css_var(fam, role)}: {p.hex(role)};'
        note = p.roles[role].get("note") if notes else None
        L.append(pad_css(decl, note) if note else decl)
    L += ["", f"{indent}/* ── ANSI 0–15 ── */"]
    slots = {int(e["i"]): e for e in p.d["ghostty"]["ansi"]}
    for i in pair["ansi"]:
        e = slots[i]
        decl = f'{indent}--{fam}-ansi-{i}: {p.hex(e["role"])};'
        L.append(pad_css(decl, e["role"]) if notes else decl)
    return L


def emit_css(pair, ctx):
    light, dark, fam = pair["light"], pair["dark"], pair["family"]
    total = len(pair["order"]) + len(pair["ansi"])
    L = ["/* ══════════════════════════════════════════════════",
         f"   🎨 {fam.capitalize()} — CSS custom properties (light + dark)",
         "   ══════════════════════════════════════════════════",
         "",
         "   ⚙️  GENERATED — не редактировать руками.",
         f"   Источник истины: {ctx['ds_sources'][0]}",
         f"                    {ctx['ds_sources'][1]}",
         f"   Пересобрать:     python3 {ctx['ds_script']} {ctx['ds_sources'][0]} --out ~/dotfiles",
         "                    (или со второй палитрой — файл выйдет байт в байт тот же)",
         "",
         "   Три состояния темы:",
         "     :root                             — полная СВЕТЛАЯ палитра;",
         "     @media (prefers-color-scheme: dark)",
         "       :root:not([data-theme=\"light\"]) — системная тёмная, но явный",
         "                                         светлый тумблер её перебивает;",
         "     :root[data-theme=\"dark\"]          — явный тёмный тумблер выигрывает",
         "                                         и у системы, и у media.",
         "",
         f"   В каждом блоке ОДИН И ТОТ ЖЕ набор из {total} переменных",
         f"   ({len(pair['order'])} ролей + {len(pair['ansi'])} ANSI). Ни одна не объявлена только",
         "   внутри media/[data-theme]: иначе у темы по умолчанию её бы",
         "   просто не было. Тёмные блоки переопределяют ТОЛЬКО токены",
         "   (и color-scheme — он не токен, а подсказка браузеру про",
         "   скроллбары и системные контролы).",
         "",
         "   Имя переменной = имя роли, подчёркивания → дефисы:",
         f"     bg_soft → {css_var(fam, 'bg_soft')}",
         "",
         "   Файл самодостаточен: подключается как есть, ничего",
         "   не импортирует. Значения — литеральные HEX, а не var()-",
         "   ссылки, чтобы любой слот читался в одно чтение.",
         "*/",
         "",
         f"/* ── {light.meta['label']} — база ── */",
         ":root {",
         "  color-scheme: light;",
         ""]
    L += _css_tokens(light, pair, "  ", notes=True)
    L += ["}",
          "",
          f"/* ── {dark.meta['label']} — системная тёмная ── */",
          "@media (prefers-color-scheme: dark) {",
          '  :root:not([data-theme="light"]) {',
          "    color-scheme: dark;",
          ""]
    L += _css_tokens(dark, pair, "    ", notes=False)
    L += ["  }",
          "}",
          "",
          f"/* ── {dark.meta['label']} — явный тумблер ── */",
          ':root[data-theme="dark"] {',
          "  color-scheme: dark;",
          ""]
    L += _css_tokens(dark, pair, "  ", notes=False)
    L += ["}"]
    return "\n".join(L) + "\n"


def theme_json(p, pair):
    bg = p.hex(p.d["ghostty"]["background"])
    raw = p.d["roles"]
    roles = {}
    for role in pair["order"]:
        spec = p.roles[role]
        roles[role] = {
            "hex": spec["hex"],
            "sh": spec.get("sh"),
            "note": spec.get("note"),
            "alias_of": raw[role].get("same_as"),
            "on": spec.get("on"),
            "min": float(spec["min"]) if "min" in spec else None,
            # Измеренный контраст против фона СВОЕЙ темы — всегда,
            # даже если роль не объявляла `on`. Именно это число
            # future-таргет покажет, не пересчитывая WCAG сам.
            "contrast_on_bg": round(contrast(spec["hex"], bg), 2),
        }
    slots = {int(e["i"]): e for e in p.d["ghostty"]["ansi"]}
    ansi = [{"index": i, "role": slots[i]["role"], "hex": p.hex(slots[i]["role"]),
             "note": slots[i].get("note")} for i in pair["ansi"]]
    g = p.d["ghostty"]
    surfaces = {k: {"role": g[k], "hex": p.hex(g[k])} for k in SURFACE_KEYS if k in g}
    return {
        "name": p.name,
        "label": p.meta["label"],
        "mode": p.meta["mode"],
        "twin": p.meta.get("twin", p.name),
        "opacity": float(p.meta["opacity"]) if "opacity" in p.meta else None,
        "source": f"tokens/{p.path.name}",
        "surfaces": surfaces,
        "roles": roles,
        "ansi": ansi,
    }


def emit_tokens_json(pair, ctx):
    light, dark = pair["light"], pair["dark"]
    doc = {
        # Ключ с $ — чтобы служебный блок не спутали с темой.
        "$generated": {
            "tool": "palette-build — design-system/build.py",
            "sources": list(ctx["ds_sources"]),
            "rebuild": f"python3 {ctx['ds_script']} {ctx['ds_sources'][0]} --out ~/dotfiles",
            # Намеренно БЕЗ timestamp: файл обязан быть байт-стабильным,
            # иначе каждый прогон даёт шум в git diff и «изменения»,
            # которых не было.
            "note": ("Машиночитаемый экспорт пары. Timestamp не пишется намеренно: "
                     "файл байт-стабилен между прогонами. Не редактировать руками — "
                     "правь tokens/*.toml и пересобирай."),
            "contrast": ("WCAG 2.x relative luminance; contrast_on_bg измерен против "
                         "ghostty.background своей темы, min — объявленный порог гейта"),
        },
        "family": pair["family"],
        "roles": list(pair["order"]),
        "themes": {light.name: theme_json(light, pair),
                   dark.name: theme_json(dark, pair)},
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"




# Zed theme schema and style-role mapping.

ZED_MAP = "zed-map.toml"
# Guard against accidentally dropping mapped style properties.
ZED_MIN_STYLE_KEYS = 136
ZED_FONT_STYLES = ("normal", "italic", "oblique")
ZED_FONT_WEIGHTS = (100, 200, 300, 400, 500, 600, 700, 800, 900)
ZED_APPEARANCES = ("light", "dark")


def load_zed_map(script_dir):
    path = script_dir / "tokens" / ZED_MAP
    if not path.exists():
        die(f"нет карты Zed: {path}")
    try:
        m = load_toml(path)
    except Exception as exc:                          # noqa: BLE001
        die(f"{ZED_MAP}: не парсится ({exc})")
    for sec in ("meta", "style", "players", "syntax"):
        if sec not in m:
            die(f"{ZED_MAP}: нет секции [{sec}]")
    for key in ("schema", "family", "author", "file"):
        if key not in m["meta"]:
            die(f"{ZED_MAP}: нет [meta].{key}")
    return m


def zed_hex(p, role, where):
    if role not in p.roles:
        die(f"{ZED_MAP} {where}: неизвестная роль '{role}' в {p.name}")
    hx = p.hex(role)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", hx):
        die(f"{ZED_MAP} {where}: роль '{role}' = '{hx}', а Zed ждёт #rrggbb")
    return hx


def zed_color(p, ref, where):
    """Три формы значения из карты:
         "gold"             → #c8a24a
         "alpha:gold:0.30"  → #c8a24a4d   (смешивает сам Zed, поэтому
                              одна альфа верна и над редактором, и над
                              гаттером, и над поповером)
         "literal:opaque"   → opaque      (мимо палитры)"""
    if not isinstance(ref, str):
        die(f"{ZED_MAP} {where}: значение должно быть строкой, а не {type(ref).__name__}")
    if ref.startswith("literal:"):
        return ref[len("literal:"):]
    if ref.startswith("alpha:"):
        parts = ref.split(":")
        if len(parts) != 3:
            die(f"{ZED_MAP} {where}: ждал alpha:<role>:<0..1>, получил '{ref}'")
        try:
            alpha = float(parts[2])
        except ValueError:
            die(f"{ZED_MAP} {where}: альфа '{parts[2]}' — не число")
        if not 0.0 <= alpha <= 1.0:
            die(f"{ZED_MAP} {where}: альфа {alpha} вне [0, 1]")
        # +0.5, а не round(): банковское округление сделало бы из
        # 0.30 байт 0x4c вместо 0x4d — мелочь, но альфы в файле
        # должны читаться теми же процентами, что записаны в карте.
        return "%s%02x" % (zed_hex(p, parts[1], where), int(alpha * 255 + 0.5))
    return zed_hex(p, ref, where)


def zed_style(p, zmap):
    style = {}
    for key, ref in zmap["style"].items():
        style[key] = zed_color(p, ref, f"[style].{key}")

    # players — массив, порядок значим: индекс 0 это сам пользователь.
    players = []
    for i, pl in enumerate(zmap["players"]):
        row = {}
        for fld in ("cursor", "background", "selection"):
            if fld not in pl:
                die(f"{ZED_MAP}: [[players]] #{i} — нет ключа {fld}")
            row[fld] = zed_color(p, pl[fld], f"[[players]] #{i}.{fld}")
        players.append(row)
    style["players"] = players


    # accents — массив, как players. Питает colorize_brackets и
    # indent_guides.background_coloring = "indent_aware". Без него
    # Zed берёт СВОЮ радугу Radix (13 цветов) и красит ею warm-тему,
    # см. crates/theme/src/styles/accents.rs. Секция необязательная:
    # старые карты без [accents] собираются как раньше.
    if "accents" in zmap:
        acc = zmap["accents"]
        if not isinstance(acc, list) or not acc:
            die(f"{ZED_MAP}: [accents] должен быть непустым списком ролей")
        style["accents"] = [zed_color(p, ref, f"accents[{i}]")
                            for i, ref in enumerate(acc)]
    syntax = {}
    for e in zmap["syntax"]:
        scope = e.get("scope")
        if not scope:
            die(f"{ZED_MAP}: в [[syntax]] есть запись без scope")
        if scope in syntax:
            die(f"{ZED_MAP}: скоуп '{scope}' объявлен дважды")
        ent = {"color": zed_color(p, e.get("color", ""), f"[[syntax]] {scope}")}
        # font_style / font_weight пишем ТОЛЬКО когда они заданы:
        # "" не входит в enum, а битую тему Zed отбрасывает молча.
        if e.get("font_style"):
            if e["font_style"] not in ZED_FONT_STYLES:
                die(f"{ZED_MAP}: [[syntax]] {scope}: font_style '{e['font_style']}' "
                    f"не из {'|'.join(ZED_FONT_STYLES)}")
            ent["font_style"] = e["font_style"]
        if e.get("font_weight"):
            if int(e["font_weight"]) not in ZED_FONT_WEIGHTS:
                die(f"{ZED_MAP}: [[syntax]] {scope}: font_weight {e['font_weight']} "
                    f"не из {ZED_FONT_WEIGHTS}")
            ent["font_weight"] = int(e["font_weight"])
        syntax[scope] = ent
    style["syntax"] = syntax
    return style


def zed_check_ansi(p, zmap, style):
    """terminal.ansi.* обязаны совпадать с [ghostty].ansi той же
    палитры — иначе один и тот же shell выглядит в Zed и в Ghostty
    двумя разными темами. Имена ролей в карте продублированы
    осознанно (ключи Zed — данные), но расхождение ловится тут."""
    by_i = {e["i"]: e["role"] for e in p.d.get("ghostty", {}).get("ansi", [])}
    for i, slot in enumerate(zmap.get("ansi", {}).get("slots", [])):
        if i not in by_i:
            die(f"{p.name}: в [ghostty].ansi нет слота {i}")
        key = "terminal.ansi." + slot
        if key not in style:
            die(f"{ZED_MAP}: нет ключа {key} (слот ANSI {i})")
        want = p.hex(by_i[i])
        if style[key].lower() != want.lower():
            die(f"{p.name}: {key} = {style[key]}, а ghostty palette={i} = {want} "
                f"({by_i[i]}) — синхронизируй [style].{key} в {ZED_MAP}")


def emit_zed(palettes, zmap):
    meta = zmap["meta"]
    themes = []
    for mode in meta.get("order", list(ZED_APPEARANCES)):
        if mode not in ZED_APPEARANCES:
            die(f"{ZED_MAP}: [meta].order — '{mode}', а Zed знает только "
                f"{'/'.join(ZED_APPEARANCES)}")
        p = palettes.get(mode)
        if p is None:
            die(f"для Zed нужна палитра mode={mode}, в паре её нет")
        style = zed_style(p, zmap)
        zed_check_ansi(p, zmap, style)
        if len(style) < ZED_MIN_STYLE_KEYS:
            die(f"{p.name}: в style {len(style)} ключей, минимум "
                f"{ZED_MIN_STYLE_KEYS} — карта {ZED_MAP} потеряла ключи")
        themes.append({"name": p.meta["label"], "appearance": mode, "style": style})
    family = {"$schema": meta["schema"], "name": meta["family"],
              "author": meta["author"], "themes": themes}
    # sort_keys: порядок ключей в JSON-объекте Zed безразличен, а нам
    # нужен байт-в-байт одинаковый файл при каждой сборке. Массивы
    # (themes, players) свой порядок сохраняют — там он значим.
    return json.dumps(family, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def run_zed(a, script_dir, out):
    base_path = Path(a.toml).expanduser() if a.toml else script_dir / "tokens" / "cameo-dark.toml"
    if not base_path.exists():
        die(f"no palette found: {base_path}")
    base = Palette(base_path)
    twin_name = base.meta.get("twin")
    if not twin_name or twin_name == base.name:
        die(f"{base.name}: meta.twin is missing")
    twin_path = base.path.parent / f"{twin_name}.toml"
    if not twin_path.exists():
        die(f"{base.name}: twin palette not found: {twin_path}")
    twin = Palette(twin_path)

    palettes = {}
    for palette in (base, twin):
        mode = palette.meta["mode"]
        if mode in palettes:
            die(f"{base.name} and {twin.name} both use mode={mode}")
        palettes[mode] = palette

    zmap = load_zed_map(script_dir)
    order = [mode for mode in zmap["meta"].get("order", list(ZED_APPEARANCES))
             if mode in palettes]
    stream = sys.stderr if a.quiet else sys.stdout
    failures = []
    for mode in order:
        failures += palettes[mode].report(stream)
    if failures:
        sys.stderr.write("\nCameo Zed palette failed contrast validation; no files written.\n")
        return 1

    text = emit_zed(palettes, zmap)
    target = out / "design-system" / "targets" / "zed" / zmap["meta"]["file"]
    results = []
    write_file(target, text, results, a.dry_run)
    for state, path in results:
        print(f"{state}: {path}")

    if a.web and not a.dry_run:
        pair, problems = load_pair(base)
        if not pair:
            sys.stderr.write("\nWeb exports skipped: " + "; ".join(problems) + "\n")
        else:
            context = {
                "ds_sources": [f"design-system/tokens/{pair['light'].path.name}",
                               f"design-system/tokens/{pair['dark'].path.name}"],
                "ds_script": "design-system/build.py",
            }
            web_results = []
            family = pair["family"]
            write_file(out / "design-system" / "targets" / "css" / f"{family}.css",
                       emit_css(pair, context), web_results, False)
            write_file(out / "design-system" / "tokens" / f"{family}.tokens.json",
                       emit_tokens_json(pair, context), web_results, False)
            for state, path in web_results:
                print(f"{state}: {path}")

    if a.dry_run:
        print("Dry run: contrast and Zed theme validation passed; no files written.")
    else:
        print("Cameo Zed theme generated. Theme activation remains explicit.")
    return 0


def main(argv=None):
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    parser = argparse.ArgumentParser(
        description="Generate Cameo's light and dark Zed theme pair.")
    parser.add_argument("toml", nargs="?", help="base palette; its meta.twin is included")
    parser.add_argument("--out", help="output repository root (default: this repository)")
    parser.add_argument("--dry-run", action="store_true", help="validate without writing files")
    parser.add_argument("--quiet", action="store_true", help="suppress contrast reports")
    parser.add_argument("--zed", action="store_true", help="legacy flag; Zed generation is now the default")
    parser.add_argument("--web", action="store_true", help="also export paired CSS and tokens.json")
    args = parser.parse_args(argv)
    out = Path(args.out).expanduser().resolve() if args.out else repo_root
    return run_zed(args, script_dir, out)


if __name__ == "__main__":
    sys.exit(main())
