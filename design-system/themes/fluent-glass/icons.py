"""Generate a Fluent Glass Zed icon extension from the Cameo glyph set."""
import json
import re
import shutil
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FAMILY = Path(__file__).resolve().parent
SOURCE = ROOT / 'design-system' / 'targets' / 'zed-icons'
OUTPUT = FAMILY / 'generated' / 'fluent-glass-icons'

# Map Cameo palette roles to the closest Fluent Glass semantic intent. Each
# source appearance keeps its own role values; only the semantic destination
# is shared across appearances.
ROLE_TARGET = {
    'fg': 'ink', 'cream': 'ink', 'paper': 'ink', 'paper_lt': 'ink',
    'dim': 'muted', 'faint': 'muted', 'subtle': 'muted', 'muted': 'muted',
    'moon': 'accent', 'moon_lt': 'accent', 'teal': 'sage', 'teal_lt': 'sage',
    'olive': 'sage', 'olive_lt': 'sage', 'terra': 'danger', 'terra_lt': 'danger',
    'rose': 'rust', 'rose_lt': 'rust', 'sand': 'rust', 'sand_lt': 'rust',
    'gold': 'warm',
}
COLOR_ROLES = tuple(ROLE_TARGET)
HEX = re.compile(r'#[0-9a-fA-F]{6}\b')


def _distance(left, right):
    """Squared RGB distance is adequate for choosing an existing palette role."""
    a = tuple(int(left[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(right[i:i + 2], 16) for i in (1, 3, 5))
    return sum((x - y) ** 2 for x, y in zip(a, b))


def _color_map(data, mode, palette):
    roles = palette['roles']
    semantic_colors = {name: data['appearances'][mode][f'--fel-{role}']
                       for name, role in {
                           'ink': 'ink-body', 'muted': 'ink-muted', 'accent': 'accent-ink',
                           'danger': 'danger', 'sage': 'sage', 'rust': 'rust', 'warm': 'warm',
                       }.items()}
    candidates = [(name, roles[name]['hex'].lower()) for name in COLOR_ROLES
                  if name in roles and 'hex' in roles[name]]
    result = {}
    for source in {color.lower() for path in (SOURCE / 'icons' / f'cameo-{mode}').glob('*.svg')
                   for color in HEX.findall(path.read_text())}:
        # The vivid blue mask is structural alpha-only art, not visible pigment.
        if source == '#3700ff':
            result[source] = source
            continue
        role = min(candidates, key=lambda pair: _distance(source, pair[1]))[0]
        result[source] = semantic_colors[ROLE_TARGET[role]]
    return result


def _replace_paths(value, mode):
    if isinstance(value, dict):
        return {key: _replace_paths(item, mode) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_paths(item, mode) for item in value]
    if isinstance(value, str):
        return value.replace(f'./icons/cameo-{mode}/', f'./icons/fluent-glass-{mode}/')
    return value


def generate(data):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Cameo palettes and the Cameo icon map are explicitly read-only inputs.
    icon_map = json.loads((SOURCE / 'icon_themes' / 'cameo-icons.json').read_text())
    themes = []
    for mode in ('light', 'dark'):
        palette = tomllib.loads((ROOT / 'design-system' / 'tokens' / f'cameo-{mode}.toml').read_text())
        colors = _color_map(data, mode, palette)
        input_dir = SOURCE / 'icons' / f'cameo-{mode}'
        output_dir = OUTPUT / 'icons' / f'fluent-glass-{mode}'
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(input_dir.glob('*.svg')):
            source = path.read_text()
            recolored = HEX.sub(lambda match: colors.get(match.group(0).lower(), match.group(0)), source)
            (output_dir / path.name).write_text(recolored)
        source_theme = next(theme for theme in icon_map['themes'] if theme['appearance'] == mode)
        theme = _replace_paths(source_theme, mode)
        theme['name'] = f'Fluent Glass {mode.title()} Icons'
        for key in ('directory_icons', 'file_icons', 'named_directory_icons'):
            # All mapping shapes come from the Cameo JSON, so preserve the exact icon coverage.
            if key not in theme:
                raise ValueError(f'Cameo icon map is missing {key}')
        themes.append(theme)

    extension = '''id = "fluent-glass-icons"\nname = "Fluent Glass Icons"\nversion = "1.0.0"\nschema_version = 1\ndescription = "Fluent Glass Light and Dark icon themes derived from Cameo glyphs."\nauthors = ["Sergey Zhechko"]\nicon_themes = ["icon_themes/fluent-glass-icons.json"]\n'''
    (OUTPUT / 'extension.toml').write_text(extension)
    (OUTPUT / 'icon_themes').mkdir(exist_ok=True)
    manifest = {
        '$schema': icon_map['$schema'],
        'author': icon_map['author'],
        'name': 'Fluent Glass Icons',
        'themes': themes,
    }
    (OUTPUT / 'icon_themes' / 'fluent-glass-icons.json').write_text(
        json.dumps(manifest, indent=2) + '\n')
    for license_name in ('LICENSE', 'LICENSE-catppuccin'):
        shutil.copyfile(SOURCE / license_name, OUTPUT / license_name)
    return OUTPUT
