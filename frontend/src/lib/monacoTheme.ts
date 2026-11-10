import type { Monaco } from '@monaco-editor/react'

export const NUDGE_MONACO_THEME = 'nudge-tokyo-mocha'

export function registerNudgeMonacoTheme(monaco: Monaco) {
  monaco.editor.defineTheme(NUDGE_MONACO_THEME, {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: '', foreground: 'cdd6f4', background: '14151f' },
      { token: 'comment', foreground: '6c7086', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'cba6f7' },
      { token: 'keyword.control', foreground: 'cba6f7' },
      { token: 'operator', foreground: '89dceb' },
      { token: 'string', foreground: 'a6e3a1' },
      { token: 'string.escape', foreground: 'f5c2e7' },
      { token: 'number', foreground: 'fab387' },
      { token: 'constant', foreground: 'fab387' },
      { token: 'type', foreground: 'f9e2af' },
      { token: 'class', foreground: 'f9e2af' },
      { token: 'function', foreground: '7aa2f7' },
      { token: 'identifier', foreground: 'cdd6f4' },
      { token: 'variable.parameter', foreground: 'eba0ac' },
      { token: 'delimiter', foreground: '9399b2' },
      { token: 'tag', foreground: 'f38ba8' },
      { token: 'attribute.name', foreground: 'f9e2af' },
      { token: 'attribute.value', foreground: 'a6e3a1' },
    ],
    colors: {
      'editor.background': '#14151f',
      'editor.foreground': '#cdd6f4',
      'editor.lineHighlightBackground': '#1e203090',
      'editor.selectionBackground': '#7aa2f733',
      'editor.inactiveSelectionBackground': '#7aa2f71a',
      'editorCursor.foreground': '#ffb86c',
      'editorLineNumber.foreground': '#45475a',
      'editorLineNumber.activeForeground': '#cba6f7',
      'editorIndentGuide.background1': '#24273a80',
      'editorIndentGuide.activeBackground1': '#585b70',
      'editorBracketMatch.background': '#7aa2f725',
      'editorBracketMatch.border': '#7aa2f780',
      'editorWidget.background': '#11121a',
      'editorWidget.border': '#2a2c3d',
      'editorSuggestWidget.background': '#11121a',
      'editorSuggestWidget.border': '#2a2c3d',
      'editorSuggestWidget.selectedBackground': '#1f2335',
      'scrollbarSlider.background': '#31324466',
      'scrollbarSlider.hoverBackground': '#45475a99',
      'scrollbarSlider.activeBackground': '#585b70aa',
      'minimap.background': '#11121a',
    },
  })
}

