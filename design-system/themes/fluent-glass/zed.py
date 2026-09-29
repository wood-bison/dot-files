"""Zed-specific role expansion. Colors belong to tokens.json, never this adapter."""

SYNTAX_ALIASES = {
    'keyword': ['keyword.control', 'keyword.declaration', 'keyword.import', 'preproc'],
    'type': ['type.builtin', 'type.class', 'enum', 'constructor', 'variant', 'tag'],
    'function': ['function.method', 'function.builtin', 'attribute'],
    'string': ['string.regex', 'string.special', 'text.literal'],
    'number': ['string.escape'],
    'boolean': ['constant', 'constant.builtin'],
    'comment': ['comment.doc'],
    'variable': ['variable.parameter', 'embedded', 'primary'],
    'property': ['variable.member', 'variable.other.member', 'property.json_key'],
    'punctuation': ['punctuation.delimiter'],
}


def make_style(data, mode):
    tokens = data['appearances'][mode]
    editor = {key: tokens[value] if value.startswith('--fel-') else value
              for key, value in data['editor'][mode].items()}

    def color(role):
        return editor[role[7:]] if role.startswith('editor:') else tokens[role]

    def web(role):
        return tokens['--fel-' + role]

    style = {key: color(role) for key, role in data['zed'].items()}
    style['background.appearance'] = 'opaque'
    groups = {
        'field': ['title_bar.inactive_background', 'editor.subheader.background', 'element.disabled', 'ghost_element.disabled'],
        'line': ['border.variant', 'border.disabled', 'pane_group.border', 'scrollbar.track.border', 'scrollbar.thumb.border', 'editor.indent_guide', 'panel.indent_guide', 'editor.wrap_guide'],
        'line-strong': ['scrollbar.thumb.background', 'editor.indent_guide_active', 'panel.indent_guide_hover', 'panel.indent_guide_active', 'editor.active_wrap_guide'],
        'ink-muted': ['text.placeholder', 'text.disabled', 'icon.muted', 'icon.disabled', 'icon.placeholder', 'editor.invisible', 'scrollbar.thumb.hover_background', 'terminal.dim_foreground'],
        'ink-body': ['icon'],
        'accent': ['border.selected', 'panel.focused_border', 'pane.focused_border', 'icon.accent', 'link_text.hover'],
        'accent-soft': ['element.active', 'ghost_element.active', 'ghost_element.selected', 'editor.highlighted_line.background', 'editor.document_highlight.read_background'],
        'plate-muted': ['ghost_element.hover'],
        'code-ink': ['terminal.foreground', 'terminal.bright_foreground'],
        'warm-soft': ['search.match_background'],
        'sage-soft': ['editor.document_highlight.write_background'],
    }
    for role, keys in groups.items():
        style.update({key: web(role) for key in keys})
    style.update({
        **{key: editor['canvas'] for key in ['background', 'editor.background', 'editor.gutter.background',
           'terminal.background', 'terminal.ansi.background', 'tab.active_background']},
        'editor.active_line.background': editor['active-line'],
        'editor.line_number': editor['line-number'],
        'editor.document_highlight.bracket_background': editor['selection'],
        'element.selected': editor['selection'],
        'scrollbar.track.background': editor['canvas'],
        'border.transparent': web('code-surface') + '00',
        'ghost_element.background': web('code-surface') + '00',
        'drop_target.background': web('accent') + '22',
    })
    for status, role in {
        'error': 'danger', 'deleted': 'danger', 'warning': 'warm', 'modified': 'warm',
        'success': 'sage', 'created': 'sage', 'info': 'accent-ink', 'renamed': 'accent-ink',
        'hint': 'ink-muted', 'ignored': 'ink-muted', 'hidden': 'ink-muted',
        'predictive': 'ink-muted', 'unreachable': 'ink-muted',
    }.items():
        value = web(role)
        style.update({status: value, status + '.background': value + '18', status + '.border': value + '88'})
    style.update({'conflict': editor['terminal-magenta'], 'conflict.background': editor['terminal-magenta'] + '18', 'conflict.border': editor['terminal-magenta'] + '88'})
    ansi = {'black': web('ink-body'), 'red': web('danger'), 'green': web('sage'),
            'yellow': web('warm'), 'blue': web('accent-ink'), 'magenta': editor['terminal-magenta'],
            'cyan': editor['terminal-cyan'], 'white': web('code-ink')}
    for name, value in ansi.items():
        for prefix in ('', 'bright_', 'dim_'):
            style['terminal.ansi.' + prefix + name] = value
    style['terminal.ansi.bright_black'] = web('ink-muted')
    syntax = {key: {'color': color(role), 'font_style': 'normal', 'font_weight': 400}
              for key, role in data['syntax'].items()}
    syntax['keyword']['font_weight'] = 600
    for role, aliases in SYNTAX_ALIASES.items():
        for alias in aliases:
            syntax[alias] = dict(syntax[role])
    syntax['punctuation.bracket'] = {'color': editor['bracket'], 'font_style': 'normal'}
    for scope, role in {'diff.plus': 'sage', 'diff.minus': 'danger', 'diff.delta': 'warm',
                        'link_text': 'accent-ink', 'link_uri': 'accent-ink',
                        'title': 'accent-ink', 'emphasis': 'ink-body', 'emphasis.strong': 'ink',
                        'markup.heading': 'accent-ink', 'markup.link.url': 'accent-ink',
                        'markup.link.text': 'accent-ink', 'markup.raw': 'code-ink',
                        'text.title': 'accent-ink', 'text.uri': 'accent-ink'}.items():
        syntax[scope] = {'color': web(role), 'font_style': 'normal'}
    syntax['emphasis.strong']['font_weight'] = 700
    style['syntax'] = syntax
    style['accents'] = [web('accent-ink'), editor['property'], web('sage'), editor['type']]
    style['players'] = [{'cursor': c, 'background': c, 'selection': editor['selection'] if i == 0 else c + '22'}
                        for i, c in enumerate([web('accent'), editor['terminal-magenta'], web('sage'), editor['terminal-cyan']])]
    return style


def validate_style(style, contrast):
    """Validate small text on the emitted opaque editor state backgrounds."""
    backgrounds = [style[k] for k in ['editor.background', 'editor.active_line.background',
                    'search.match_background', 'editor.document_highlight.read_background',
                    'editor.document_highlight.write_background']]
    backgrounds.append(style['players'][0]['selection'])
    results = []
    for scope, token in style['syntax'].items():
        ratio = min(contrast(token['color'], bg) for bg in backgrounds)
        if ratio < 4.5:
            raise ValueError(f'{scope}: contrast {ratio:.2f} < 4.5 on editor state')
        results.append(ratio)
    for key in ['editor.line_number', 'editor.active_line_number']:
        ratio = contrast(style[key], style['editor.background'])
        if ratio < 4.5:
            raise ValueError(f'{key}: contrast {ratio:.2f} < 4.5')
    return min(results)
