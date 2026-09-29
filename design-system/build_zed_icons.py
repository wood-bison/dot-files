#!/usr/bin/env python3
# ══════════════════════════════════════════════════
# 🎨 Zed icons sink — генератор темы «Cameo Icons»
# ══════════════════════════════════════════════════
# Единственный источник цвета: design-system/tokens/cameo-*.toml.
# Единственный источник геометрии: установленное расширение
# catppuccin-icons (читается ТОЛЬКО на чтение).
# Карта «HEX апстрима → роль Cameo» — данные, лежат в
# zed-icons-map.toml рядом.
#
# Файл написан так, чтобы целиком уехать в build.py:
# emit_zed_icons(palettes, imap) повторяет форму emit_zed(palettes, zmap),
# гейт падает с exit 1 и НЕ ПИШЕТ НИЧЕГО — как везде в проекте.
#
#   python3 build_zed_icons.py --out ./cameo-icons
#   python3 build_zed_icons.py --dry-run
#
# stdlib only.
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:                       # 3.9 / 3.10
    tomllib = None

MAP_FILE = "zed-icons-map.toml"
ZED_APPEARANCES = ("light", "dark")
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


# ──────────────────────────────────────────────────
#  Хелперы (те же, что в build.py)
# ──────────────────────────────────────────────────
def die(msg):
    sys.stderr.write(f"zed-icons: ❌ {msg}\n")
    sys.exit(1)


def load_toml(path):
    if tomllib is None:
        die("нужен Python 3.11+ (tomllib). В build.py есть мини-парсер — "
            "при переносе туда используй его load_toml().")
    with open(path, "rb") as f:
        return tomllib.load(f)


def _unquote_keys(obj):
    """Мини-парсер build.py отдаёт цитированный ключ вместе с кавычками
    ('"#4c4f69"'), tomllib так не делает. Нормализуем, чтобы карта
    читалась одинаково на обоих бэкендах."""
    if isinstance(obj, dict):
        return {k.strip('"'): _unquote_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unquote_keys(v) for v in obj]
    return obj


def rgb(hex_):
    h = hex_.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_):
    r, g, b = (_lin(c) for c in rgb(hex_))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


# ──────────────────────────────────────────────────
#  OKLab — перцептивная середина двух ролей
# ──────────────────────────────────────────────────
# Смесь берём в OKLab, а не в sRGB: середина в sRGB между
# moon и teal уходит в серую грязь, в OKLab — остаётся цветом.
def _srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def hex_to_oklab(h):
    r, g, b = (_srgb_to_lin(c / 255) for c in rgb(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_to_hex(L, a, bb):
    l = (L + 0.3963377774 * a + 0.2158037573 * bb) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * bb) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * bb) ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    out = []
    for c in (r, g, b):
        out.append(max(0, min(255, round(_lin_to_srgb(max(0.0, min(1.0, c))) * 255))))
    return "#%02x%02x%02x" % tuple(out)


def mix_oklab(h1, h2, t):
    A, B = hex_to_oklab(h1), hex_to_oklab(h2)
    return oklab_to_hex(*(A[i] + (B[i] - A[i]) * t for i in range(3)))


def oklab_de(h1, h2):
    A, B = hex_to_oklab(h1), hex_to_oklab(h2)
    return sum((A[i] - B[i]) ** 2 for i in range(3)) ** 0.5


# ──────────────────────────────────────────────────
#  Палитра (усечённый Palette из build.py)
# ──────────────────────────────────────────────────
class Palette:
    def __init__(self, path):
        self.path = Path(path)
        self.d = load_toml(path)
        self.meta = self.d["meta"]
        self.name = self.meta["name"]
        self.mode = self.meta["mode"]
        raw = self.d["roles"]
        self.roles = {}
        for key, spec in raw.items():
            src = spec
            if "same_as" in spec:
                base = raw[spec["same_as"]]
                src = {**base, **{k: v for k, v in spec.items() if k != "same_as"}}
                src["hex"] = base["hex"]
            if "hex" not in src:
                die(f"{self.name}: роль '{key}' без hex и без same_as")
            self.roles[key] = src

    def hex(self, role):
        if role not in self.roles:
            die(f"{self.name}: неизвестная роль '{role}' "
                f"(есть: {', '.join(sorted(self.roles))})")
        hx = self.roles[role]["hex"]
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", hx):
            die(f"{self.name}: роль '{role}' = '{hx}', а SVG ждёт #rrggbb")
        return hx


def map_path(script_dir):
    """tokens/<map> — как zed-map.toml у build.py. Рядом со скриптом —
    запасной путь, чтобы то же дерево запускалось из стейджинга."""
    for p in (script_dir / "tokens" / MAP_FILE, script_dir / MAP_FILE):
        if p.exists():
            return p
    return script_dir / "tokens" / MAP_FILE


def load_map(script_dir):
    path = map_path(script_dir)
    if not path.exists():
        die(f"нет карты иконок: {path}")
    try:
        m = _unquote_keys(load_toml(path))
    except Exception as exc:                       # noqa: BLE001
        die(f"{MAP_FILE}: не парсится ({exc})")
    for sec in ("meta", "themes", "source_hex", "structural", "accents"):
        if sec not in m:
            die(f"{MAP_FILE}: нет секции [{sec}]")
    for key in ("schema", "family", "author", "file", "extension_id",
                "version", "source_extension", "gate_on", "min_contrast"):
        if key not in m["meta"]:
            die(f"{MAP_FILE}: нет [meta].{key}")
    return m


# ──────────────────────────────────────────────────
#  Акцент апстрима → HEX Cameo
# ──────────────────────────────────────────────────
def accent_palette(p, imap):
    """Одна форма значения на акцент: role ЛИБО mix+t."""
    out = {}
    for accent, spec in imap["accents"].items():
        has_role, has_mix = "role" in spec, "mix" in spec
        if has_role == has_mix:
            die(f"{MAP_FILE}: [accents.{accent}] — нужен ровно один из role / mix")
        if has_role:
            out[accent] = p.hex(spec["role"])
            continue
        anchors = spec["mix"]
        if not isinstance(anchors, list) or len(anchors) != 2:
            die(f"{MAP_FILE}: [accents.{accent}].mix — ждал две роли, получил {anchors!r}")
        if "t" not in spec:
            die(f"{MAP_FILE}: [accents.{accent}] — есть mix, нет t")
        t = float(spec["t"])
        if not 0.0 <= t <= 1.0:
            die(f"{MAP_FILE}: [accents.{accent}].t = {t} вне [0, 1]")
        out[accent] = mix_oklab(p.hex(anchors[0]), p.hex(anchors[1]), t)
    return out


def gate(p, imap, pal):
    """WCAG 1.4.11: иконка — non-text content, планка 3:1.
    Меряем против ХУДШЕЙ из подложек в [meta].gate_on."""
    floor = float(imap["meta"]["min_contrast"])
    rows, failures = [], []
    for accent in sorted(pal):
        hx = pal[accent]
        ratios = {g: contrast(hx, p.hex(g)) for g in imap["meta"]["gate_on"]}
        worst_on = min(ratios, key=ratios.get)
        worst = ratios[worst_on]
        ok = worst + 1e-9 >= floor
        rows.append((accent, hx, ratios, worst, worst_on, ok))
        if not ok:
            failures.append(f"accent {accent} ({hx}) на {worst_on}: {worst:.2f} < min {floor}")
    return rows, failures


# ──────────────────────────────────────────────────
#  Перекраска SVG (в память, до единой записи)
# ──────────────────────────────────────────────────
# Геометрия дуотон-чипа. viewBox апстрима 16×16; рамочные иконки
# ведут контур по 1.5 со stroke 1.1 (внутренний край ≈2.05), поэтому
# чип начинается на 1.9: внутри рамки, без щели; у бесрамочных
# силуэтов читается почти во всю плашку. Подробности — [duotone]
# в zed-icons-map.toml.
CHIP = '<rect x="1.9" y="1.9" width="12.2" height="12.2" rx="2.4" fill="{hex}" fill-opacity="{alpha:g}"/>'
STROKE_RE = re.compile(r'stroke="(#[0-9a-fA-F]{6})"')


def apply_duotone(name, text, alpha, exclude):
    """Вставить фон-чип первым элементом после <svg…>.

    Цвет чипа — ПЕРВЫЙ stroke файла, то есть акцент, который
    перекраска уже положила в этот SVG: новых HEX не появляется,
    проверка остаточных проходит как раньше. Файлы без явного
    stroke (poetry-lock с url(#a)) молча пропускаются — их немного,
    и чип им дал бы пустой квадрат.
    """
    if name.startswith(exclude):
        return text, False
    m = STROKE_RE.search(text)
    if not m:
        return text, False
    chip = CHIP.format(hex=m.group(1), alpha=alpha)
    text, n = re.subn(r"(<svg\b[^>]*>)", lambda mm: mm.group(1) + chip, text, count=1)
    return text, n == 1


def recolour(src_dir, subs, allowed, duo=None):
    """Возвращает (имя → текст), список битых XML и остаточные HEX.
    Ничего не пишет: сначала считаем всё, потом гейт, потом запись."""
    files, broken, residual = {}, [], {}
    pat = re.compile("|".join(re.escape(k) for k in sorted(subs, key=len, reverse=True)),
                     re.IGNORECASE)
    for f in sorted(src_dir.glob("*.svg")):
        text = pat.sub(lambda m: subs[m.group(0).lower()], f.read_text(encoding="utf-8"))
        chipped = False
        if duo:
            text, chipped = apply_duotone(f.name, text, *duo)
        try:
            ET.fromstring(text)                    # регулярка могла порвать разметку
        except ET.ParseError as exc:
            broken.append(f"{f.name}: {exc}")
        for h in HEX_RE.findall(text):
            if h.lower() not in allowed:
                residual.setdefault(h.lower(), []).append(f.name)
        files[f.name] = (text, chipped)
    return files, broken, residual


# ──────────────────────────────────────────────────
#  Тема: пути + имена, НИ ОДНОГО цвета
# ──────────────────────────────────────────────────
def apply_overlay(theme, overlay, spec, have_svg):
    """Единственное отличие от апстрима не по цвету. Цель обязана
    существовать в file_icons ЭТОЙ темы: Zed при промахе уходит в
    дефолтную тему (file_icons.rs: get_icon_for_type → or_else →
    default_icon_theme), то есть опечатка не упала бы, а тихо
    подсунула чужую иконку."""
    added = {}
    for key, fname in (overlay.get("file_icons") or {}).items():
        if fname not in have_svg:
            die(f"{MAP_FILE}: [overlay.file_icons] '{key}' → '{fname}', "
                f"а такого SVG в наборе нет")
        if key in theme["file_icons"]:
            die(f"{MAP_FILE}: [overlay.file_icons] '{key}' уже есть у апстрима — "
                f"overlay только добавляет")
        theme["file_icons"][key] = {"path": f"./icons/{spec['dir']}/{fname}"}
        added[f"file_icons.{key}"] = fname
    theme["file_icons"] = dict(sorted(theme["file_icons"].items()))
    for field in ("file_suffixes", "file_stems"):
        for key, target in (overlay.get(field) or {}).items():
            if target not in theme["file_icons"]:
                die(f"{MAP_FILE}: [overlay.{field}] '{key}' → '{target}', "
                    f"а такой иконки в file_icons нет")
            theme[field][key] = target
            added[f"{field}.{key}"] = target
        theme[field] = dict(sorted(theme[field].items()))
    return added


def theme_json(src_theme, spec):
    """Схема icon_themes не имеет ни одного цветового свойства
    (IconDefinitionContent = {"path": string}), поэтому перенос —
    это только переименование темы и подмена каталога в путях."""
    old = f"./icons/{spec['source_flavour']}/"
    new = f"./icons/{spec['dir']}/"

    def path(v):
        if v is None:
            return None
        if not v.startswith(old):
            die(f"тема '{src_theme['name']}': путь '{v}' не из {old}")
        return new + v[len(old):]

    def dirs(d):
        return {"collapsed": path(d.get("collapsed")), "expanded": path(d.get("expanded"))}

    return {
        "name": spec["name"],
        "appearance": spec["appearance"],
        "directory_icons": dirs(src_theme.get("directory_icons", {})),
        "chevron_icons": {                          # None = не переопределяем;
            "collapsed": None,                      # шеврон рисует сам Zed и
            "expanded": None,                       # красит его ЦВЕТОВОЙ темой
        } if not any((src_theme.get("chevron_icons") or {}).values())
        else dirs(src_theme["chevron_icons"]),
        "named_directory_icons": {k: dirs(v) for k, v
                                  in sorted(src_theme.get("named_directory_icons", {}).items())},
        "file_stems": dict(sorted(src_theme.get("file_stems", {}).items())),
        "file_suffixes": dict(sorted(src_theme.get("file_suffixes", {}).items())),
        "file_icons": {k: {"path": path(v["path"])} for k, v
                       in sorted(src_theme.get("file_icons", {}).items())},
    }


def emit_zed_icons(palettes, imap, src_root):
    """Форма повторяет emit_zed(palettes, zmap): считает ВСЁ,
    падает до записи, возвращает (файлы, отчёт)."""
    meta = imap["meta"]
    src_json_path = src_root / "icon_themes" / f"{meta['source_extension']}.json"
    if not src_json_path.exists():
        die(f"нет исходной темы: {src_json_path}")
    src_json = json.loads(src_json_path.read_text(encoding="utf-8"))
    by_name = {t["name"]: t for t in src_json["themes"]}

    structural = {k.lower() for k in imap["structural"]}
    blob, themes, report, failures = {}, [], {}, []

    for spec in imap["themes"]:
        if spec["appearance"] not in ZED_APPEARANCES:
            die(f"{MAP_FILE}: appearance '{spec['appearance']}' — Zed знает только "
                f"{'/'.join(ZED_APPEARANCES)}")
        p = palettes.get(spec["mode"])
        if p is None:
            die(f"для темы '{spec['name']}' нужна палитра mode={spec['mode']}")
        if spec["source_name"] not in by_name:
            die(f"в {src_json_path.name} нет темы '{spec['source_name']}' "
                f"(есть: {', '.join(sorted(by_name))})")

        pal = accent_palette(p, imap)
        rows, fails = gate(p, imap, pal)
        failures += fails

        src_hex = imap["source_hex"].get(spec["source_flavour"])
        if not src_hex:
            die(f"{MAP_FILE}: нет [source_hex.{spec['source_flavour']}]")
        subs = {}
        for hx, accent in src_hex.items():
            if accent not in pal:
                die(f"{MAP_FILE}: [source_hex.{spec['source_flavour']}] {hx} → "
                    f"'{accent}', а такого [accents.{accent}] нет")
            subs[hx.lower()] = pal[accent]

        src_dir = src_root / "icons" / spec["source_flavour"]
        if not src_dir.is_dir():
            die(f"нет исходных SVG: {src_dir}")
        allowed = {v.lower() for v in pal.values()} | structural
        # Дуотон-чип ([duotone] карты): alpha берётся по appearance темы.
        duo = None
        if "duotone" in imap:
            d = imap["duotone"]
            if spec["appearance"] not in d:
                die(f"{MAP_FILE}: [duotone] нет ключа '{spec['appearance']}'")
            duo = (float(d[spec["appearance"]]), tuple(d.get("exclude_prefixes", [])))
        files, broken, residual = recolour(src_dir, subs, allowed, duo)
        if broken:
            failures += [f"{spec['name']}: битый XML после подстановки — {b}" for b in broken[:5]]
        if residual:
            failures += [f"{spec['name']}: остаточный HEX {h} в "
                         f"{len(v)} файл(ах), напр. {v[0]}" for h, v in residual.items()]

        for fname, (text, _) in files.items():
            blob[f"icons/{spec['dir']}/{fname}"] = text
        theme = theme_json(by_name[spec["source_name"]], spec)
        added = apply_overlay(theme, imap.get("overlay", {}), spec, set(files))
        themes.append(theme)

        # самая тесная пара — честная цена сжатия 16 акцентов в 7 ролей
        names = sorted(pal)
        tight = min(((oklab_de(pal[a], pal[b]), a, b)
                     for i, a in enumerate(names) for b in names[i + 1:]),
                    key=lambda x: x[0])
        report[spec["name"]] = {
            "palette": {a: hx for a, hx in sorted(pal.items())},
            "svg": len(files),
            "duotone": sum(1 for _, c in files.values() if c),
            "overlay": added,
            "worst_contrast": round(min(r[3] for r in rows), 2),
            "tightest_pair": [tight[1], tight[2], round(tight[0], 4)],
            "rows": rows,
        }

    if failures:
        return None, report, failures

    family = {"$schema": meta["schema"], "name": meta["family"],
              "author": meta["author"], "themes": themes}
    # sort_keys: порядок ключей в JSON-объекте Zed безразличен, а нам нужен
    # байт-в-байт одинаковый файл при каждой сборке. Массив themes порядок
    # сохраняет — там он значим (light, затем dark).
    blob[f"icon_themes/{meta['file']}"] = json.dumps(
        family, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    blob["extension.toml"] = extension_toml(imap)
    return blob, report, []


def extension_toml(imap):
    m = imap["meta"]
    return (
        "# ⚙️  GENERATED — не редактировать руками.\n"
        f"# Источник истины: design-system/tokens/cameo-*.toml + {MAP_FILE}\n"
        "# Пересобрать:     python3 build_zed_icons.py --out <dir>\n"
        "\n"
        f'id = "{m["extension_id"]}"\n'
        f'name = "{m["family"]}"\n'
        f'version = "{m["version"]}"\n'
        "schema_version = 1\n"
        'description = "Cameo icon theme for Zed — the same roles as the terminal. '
        'Recoloured from Catppuccin Icons (MIT)."\n'
        f'authors = ["{m["author"]}"]\n'
        f'repository = "{m["repository"]}"\n'
        "\n"
        "# Явный список: Zed автодополняет его сканом каталога, только\n"
        "# когда ключа нет. Пишем явно — как это делает апстрим.\n"
        f'icon_themes = ["icon_themes/{m["file"]}"]\n')


def vendor(imap, src_root, dst):
    """Скопировать минимум донора внутрь design-system.

    Зачем: как только Cameo Icons заработает, catppuccin-icons захочется
    удалить — и генератор потеряет источник геометрии, то есть сток
    перестанет пересобираться. Это ломает главный принцип проекта.

    Хватает ОДНОГО флейвора: геометрия latte и mocha совпадает
    побайтово после вырезания HEX (проверено на всех 656 файлах),
    поэтому обе темы Cameo можно генерить из одного набора.
    После этого в [[themes]] у обеих тем ставится один и тот же
    source_flavour / source_name, а [source_hex] схлопывается
    в одну таблицу."""
    flavours = {t["source_flavour"] for t in imap["themes"]}
    pick = sorted(flavours)[0] if len(flavours) == 1 else "mocha"
    names = {t["source_name"] for t in imap["themes"]}
    src_json = json.loads(
        (src_root / "icon_themes" / f"{imap['meta']['source_extension']}.json")
        .read_text(encoding="utf-8"))
    keep = [t for t in src_json["themes"] if t["name"] in names or
            t["name"].lower().endswith(pick)]
    if not keep:
        die(f"в доноре нет темы под флейвор '{pick}'")
    slim = {**{k: v for k, v in src_json.items() if k != "themes"}, "themes": keep}
    (dst / "icon_themes").mkdir(parents=True, exist_ok=True)
    (dst / "icon_themes" / f"{imap['meta']['source_extension']}.json").write_text(
        json.dumps(slim, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8")
    n = 0
    out_dir = dst / "icons" / pick
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted((src_root / "icons" / pick).glob("*.svg")):
        (out_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
        n += 1
    print(f"  вендор: флейвор '{pick}', {n} SVG + тема → {dst}")
    print(f"  дальше: build_zed_icons.py --src {dst} …  (донор больше не нужен)")
    return 0


# ──────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────
def main(argv=None):
    script_dir = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Cameo icon theme for Zed")
    ap.add_argument("--tokens", default=str(Path.home() / "dotfiles/design-system/tokens"),
                    help="каталог с cameo-dark.toml / cameo-light.toml (только чтение)")
    ap.add_argument("--src", default=str(Path.home() / "Library/Application Support/Zed"
                                                       "/extensions/installed/catppuccin-icons"),
                    help="установленное расширение-донор (только чтение)")
    ap.add_argument("--out", default=str(script_dir / "targets" / "zed-icons"),
                    help="корень расширения на выходе")
    ap.add_argument("--dry-run", action="store_true", help="посчитать и показать, не писать")
    ap.add_argument("--vendor", metavar="DIR",
                    help="сложить донора внутрь design-system и выйти: генератор "
                         "перестанет зависеть от установленного расширения")
    a = ap.parse_args(argv)

    imap = load_map(script_dir)
    tokens = Path(a.tokens)
    palettes = {}
    for mode in ZED_APPEARANCES:
        f = tokens / f"cameo-{mode}.toml"
        if not f.exists():
            die(f"нет палитры {f}")
        p = Palette(f)
        if p.mode != mode:
            die(f"{f.name}: [meta].mode = '{p.mode}', ожидался '{mode}'")
        palettes[mode] = p

    src_root = Path(a.src)
    if not src_root.is_dir():
        die(f"нет расширения-донора: {src_root}")

    if a.vendor:
        return vendor(imap, src_root, Path(a.vendor))

    blob, report, failures = emit_zed_icons(palettes, imap, src_root)

    floor = imap["meta"]["min_contrast"]
    for name, r in report.items():
        print(f"\n  🎨 {name} — {r['svg']} SVG, {len(r['palette'])} акцентов, "
              f"дуотон: {r['duotone']} чипов")
        print(f"  {'акцент':<11} {'hex':<9} " +
              " ".join(f"{g:>9}" for g in imap["meta"]["gate_on"]) + "   gate")
        print("  " + "─" * 52)
        for accent, hx, ratios, worst, worst_on, ok in r["rows"]:
            cells = " ".join(f"{ratios[g]:>9.2f}" for g in imap["meta"]["gate_on"])
            print(f"  {accent:<11} {hx:<9} {cells}   {'PASS' if ok else 'FAIL'}")
        t = r["tightest_pair"]
        print(f"  худший контраст {r['worst_contrast']}:1 (планка {floor}:1, WCAG 1.4.11) · "
              f"теснейшая пара {t[0]}/{t[1]} ΔE_OK {t[2]}")
        if r["overlay"]:
            print(f"  overlay (+{len(r['overlay'])} правил сверх апстрима): "
                  + ", ".join(f"{k.split('.', 1)[1]} → {v}" for k, v in r["overlay"].items()))

    if failures:
        sys.stderr.write(f"\n  ❌ гейт не пройден — {len(failures)} нарушени(й), "
                         f"НИЧЕГО НЕ ЗАПИСАНО:\n")
        for f in failures:
            sys.stderr.write(f"     • {f}\n")
        sys.exit(1)

    print(f"\n  ✅ гейт пройден — {sum(r['svg'] for r in report.values())} SVG, "
          f"{len(report)} темы, 0 остаточных HEX, 0 битых XML")

    if a.dry_run:
        print("  (--dry-run: ничего не записано)")
        return 0

    out = Path(a.out)
    for rel, text in sorted(blob.items()):
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    # MIT требует, чтобы уведомление ехало вместе с производной
    lic = script_dir / "LICENSE-catppuccin"
    if not lic.exists():
        die(f"нет {lic} — MIT требует везти уведомление с производной")
    (out / "LICENSE-catppuccin").write_text(lic.read_text(encoding="utf-8"), encoding="utf-8")
    # Своя лицензия — отдельно от катппуччиновской. Требование реестра
    # Zed: файл LICENSE* должен лежать ВНУТРИ каталога расширения;
    # лицензия в корне репозитория не засчитывается.
    own = script_dir / "LICENSE"
    if not own.exists():
        die(f"нет {own} — реестр Zed не примет расширение без лицензии")
    (out / "LICENSE").write_text(own.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  записано: {len(blob) + 2} файл(ов) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
