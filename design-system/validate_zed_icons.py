#!/usr/bin/env python3
"""Проверка собранного расширения — отдельно от сборки, чтобы гейт
и проверка не могли ошибиться одинаково.

Валидируем против icon-theme-schema.json — это draft-07, выведенный
из Rust-структур самого Zed (IconThemeFamilyContent / IconThemeContent /
IconDefinitionContent), а не против URL: URL Zed не читает, он вообще
не поле структуры.

Пути резолвим ровно как Zed: ThemeRegistry::load_icon_theme делает
icons_root_dir.join(path), где icons_root_dir — корень расширения.

  python3 validate_zed_icons.py [--ext ./cameo-icons]
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
OK, BAD = "  ✅", "  ❌"
fails = []


def check(cond, ok_msg, bad_msg):
    if cond:
        print(f"{OK} {ok_msg}")
    else:
        print(f"{BAD} {bad_msg}")
        fails.append(bad_msg)
    return cond


# ── 1. минимальный валидатор draft-07 под нужное подмножество ──────────
def validate(node, schema, root, where):
    """Поддерживаем ровно то, что есть в схеме Zed: $ref, type, enum,
    required, properties, additionalProperties, items, anyOf, allOf."""
    errs = []
    if "$ref" in schema:
        return validate(node, resolve(schema["$ref"], root), root, where)
    if "allOf" in schema:
        for s in schema["allOf"]:
            errs += validate(node, s, root, where)
    if "anyOf" in schema:
        if not any(not validate(node, s, root, where) for s in schema["anyOf"]):
            errs.append(f"{where}: не подходит ни под один вариант anyOf")
    t = schema.get("type")
    if t == "object":
        if not isinstance(node, dict):
            return errs + [f"{where}: ждал object, получил {type(node).__name__}"]
        for r in schema.get("required", []):
            if r not in node:
                errs.append(f"{where}: нет обязательного ключа '{r}'")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties")
        for k, v in node.items():
            if k in props:
                errs += validate(v, props[k], root, f"{where}.{k}")
            elif isinstance(addl, dict):
                errs += validate(v, addl, root, f"{where}[{k}]")
    elif t == "array":
        if not isinstance(node, list):
            return errs + [f"{where}: ждал array"]
        for i, v in enumerate(node):
            errs += validate(v, schema.get("items", {}), root, f"{where}[{i}]")
    elif t == "string":
        if not isinstance(node, str):
            errs.append(f"{where}: ждал string, получил {type(node).__name__}")
    elif t == "null":
        if node is not None:
            errs.append(f"{where}: ждал null")
    if "enum" in schema and node not in schema["enum"]:
        errs.append(f"{where}: '{node}' не из {schema['enum']}")
    if "required" in schema and "type" not in schema and isinstance(node, dict):
        for r in schema["required"]:
            if r not in node:
                errs.append(f"{where}: нет обязательного ключа '{r}'")
    if "properties" in schema and "type" not in schema and isinstance(node, dict):
        for k, v in node.items():
            if k in schema["properties"]:
                errs += validate(v, schema["properties"][k], root, f"{where}.{k}")
    return errs


def resolve(ref, root):
    node = root
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    # Артефакты живут в targets/zed-icons — старый дефолт (here/"cameo-icons")
    # указывал в никуда, и запуск без аргументов падал трейсбеком.
    ap.add_argument("--ext", default=str(
        next((p for p in (here / "targets" / "zed-icons",
                          here / "cameo-icons") if p.exists()),
             here / "targets" / "zed-icons")))
    ap.add_argument("--map", default=str(
        next((p for p in (here / "tokens" / "zed-icons-map.toml",
                          here / "zed-icons-map.toml") if p.exists()),
             here / "zed-icons-map.toml")))
    ap.add_argument("--schema", default=str(
        next((p for p in (here / "docs" / "icon-theme-schema.json",
                          here / "icon-theme-schema.json") if p.exists()),
             here / "docs" / "icon-theme-schema.json")))
    a = ap.parse_args()
    ext = Path(a.ext)

    print(f"\n  корень расширения: {ext}")

    # ── extension.toml ────────────────────────────────────────────────
    man_path = ext / "extension.toml"
    check(man_path.exists(), "extension.toml на месте", "нет extension.toml")
    man = tomllib.loads(man_path.read_text()) if tomllib else {}
    for k in ("id", "name", "version", "schema_version", "icon_themes"):
        check(k in man, f"extension.toml: есть {k} = {man.get(k)!r}",
              f"extension.toml: нет ключа {k}")
    for rel in man.get("icon_themes", []):
        check((ext / rel).is_file(), f"extension.toml → {rel} существует",
              f"extension.toml ссылается на несуществующий {rel}")

    # ── JSON парсится ─────────────────────────────────────────────────
    jpath = ext / man["icon_themes"][0]
    try:
        fam = json.loads(jpath.read_text(encoding="utf-8"))
        print(f"{OK} JSON парсится ({jpath.stat().st_size // 1024} KB)")
    except json.JSONDecodeError as exc:
        check(False, "", f"JSON не парсится: {exc}")
        return 1

    # ── схема ─────────────────────────────────────────────────────────
    schema = json.loads(Path(a.schema).read_text())
    body = {k: v for k, v in fam.items() if k != "$schema"}   # $schema не поле структуры
    errs = validate(body, schema, schema, "root")
    check(not errs, f"схема IconThemeFamilyContent: соответствует "
                    f"({len(fam['themes'])} темы)",
          f"схема: {len(errs)} нарушени(й) — {errs[:3]}")

    modes = sorted(t["appearance"] for t in fam["themes"])
    check(modes == ["dark", "light"],
          f'appearance: {modes} — "mode": "system" получит обе ветки',
          f"appearance: {modes} — для system нужны ровно light и dark")

    # ── пути: ровно как icons_root_dir.join(path) в Zed ───────────────
    refs, missing = [], []
    for t in fam["themes"]:
        buckets = [t.get("directory_icons") or {}, t.get("chevron_icons") or {}]
        buckets += list((t.get("named_directory_icons") or {}).values())
        for b in buckets:
            refs += [(t["name"], v) for v in b.values() if v]
        refs += [(t["name"], d["path"]) for d in (t.get("file_icons") or {}).values()]
    for theme, rel in refs:
        if not (ext / rel).is_file():
            missing.append(f"{theme}: {rel}")
    uniq = {rel for _, rel in refs}
    check(not missing,
          f"пути: {len(refs)} ссылок на {len(uniq)} уникальных файлов — все существуют",
          f"пути: {len(missing)} битых из {len(refs)} (напр. {missing[:3]})")

    # ── file_icons ЗАМЕНЯЕТСЯ целиком (в отличие от stems/suffixes,
    #    которые Zed мержит с дефолтной темой) → цели обязаны быть свои
    dangling = []
    for t in fam["themes"]:
        keys = set((t.get("file_icons") or {}).keys())
        for field in ("file_suffixes", "file_stems"):
            for k, v in (t.get(field) or {}).items():
                if v not in keys:
                    dangling.append(f"{t['name']}.{field}['{k}'] → '{v}'")
    check(not dangling,
          f"суффиксы и стемы: все цели есть в file_icons "
          f"({len(fam['themes'][0].get('file_suffixes', {}))} суффиксов, "
          f"{len(fam['themes'][0].get('file_stems', {}))} стемов)",
          f"висячих целей: {len(dangling)} (напр. {dangling[:3]})")

    # ── SVG: XML + остаточные HEX ─────────────────────────────────────
    imap = tomllib.loads(Path(a.map).read_text())
    structural = {k.lower() for k in imap["structural"]}
    broken, residual, on_disk = [], {}, set()
    for svg in sorted((ext / "icons").rglob("*.svg")):
        on_disk.add(str(svg.relative_to(ext)))
        text = svg.read_text(encoding="utf-8")
        try:
            ET.fromstring(text)
        except ET.ParseError as exc:
            broken.append(f"{svg.name}: {exc}")
        for h in HEX_RE.findall(text):
            residual.setdefault(h.lower(), set()).add(svg.parent.name)
    check(not broken, f"XML: все {len(on_disk)} SVG разбираются",
          f"битый XML: {len(broken)} (напр. {broken[:2]})")

    # ── откуда взялся каждый HEX в выводе ─────────────────────────────
    # Цветной HEX имеет право быть либо ролью палитры (прямое
    # соответствие), либо серединой двух ролей в OKLab (смесь).
    # Всё, что не то и не другое, — след апстрима, это провал.
    tokens_dir = Path.home() / "dotfiles/design-system/tokens"
    role_hex = set()
    for f in ("cameo-light.toml", "cameo-dark.toml"):
        d = tomllib.loads((tokens_dir / f).read_text())
        role_hex |= {v["hex"].lower() for v in d["roles"].values() if "hex" in v}
    mixes = {a: s for a, s in imap["accents"].items() if "mix" in s}
    sys.path.insert(0, str(here))
    from build_zed_icons import mix_oklab           # тот же OKLab, что при сборке
    mix_hex = set()
    for f, mode in (("cameo-light.toml", "light"), ("cameo-dark.toml", "dark")):
        roles = tomllib.loads((tokens_dir / f).read_text())["roles"]
        for spec in mixes.values():
            mix_hex.add(mix_oklab(roles[spec["mix"][0]]["hex"],
                                  roles[spec["mix"][1]]["hex"], spec["t"]).lower())
    unexplained = {h: sorted(v) for h, v in residual.items()
                   if h not in structural and h not in role_hex and h not in mix_hex}
    check(not unexplained,
          f"HEX в выводе: {len(residual)} уникальных — "
          f"{len(set(residual) & role_hex)} ролей палитры, "
          f"{len(set(residual) & mix_hex - role_hex)} смесей OKLab, "
          f"{len(set(residual) & structural)} структурных, 0 чужих",
          f"необъяснимые HEX (след апстрима): {unexplained}")
    print(f"     структурные, оставлены как есть: "
          f"{', '.join(sorted(structural & set(residual)))}")

    # ── сироты: файл есть, ссылок нет ────────────────────────────────
    orphans = sorted(on_disk - {r.lstrip("./") for r in uniq})
    print(f"  ℹ️  сироты (файл лежит, ссылок из JSON нет): {len(orphans)}"
          + (f" — напр. {orphans[:3]}" if orphans else ""))

    # ── лицензия ─────────────────────────────────────────────────────
    check((ext / "LICENSE-catppuccin").is_file(),
          "LICENSE-catppuccin едет вместе с производной (требование MIT)",
          "нет LICENSE-catppuccin — MIT нарушен")

    print()
    if fails:
        print(f"  ❌ проверка не пройдена: {len(fails)} нарушени(й)")
        return 1
    print("  ✅ проверка пройдена")
    return 0


if __name__ == "__main__":
    sys.exit(main())
