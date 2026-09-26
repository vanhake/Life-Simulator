"""pygame_gui theme matching the dark side panel."""

GUI_THEME = {
    "defaults": {
        "colours": {
            "dark_bg": "#1a1a19",
            "normal_bg": "#262624",
            "hovered_bg": "#383835",
            "disabled_bg": "#1a1a19",
            "selected_bg": "#256abf",
            "active_bg": "#256abf",
            "normal_text": "#ffffff",
            "hovered_text": "#ffffff",
            "selected_text": "#ffffff",
            "active_text": "#ffffff",
            "disabled_text": "#8c8b83",
            "normal_border": "#383835",
            "hovered_border": "#8c8b83",
            "selected_border": "#3987e5",
            "active_border": "#3987e5",
            "disabled_border": "#262624",
            "filled_bar": "#3987e5",
            "unfilled_bar": "#383835",
        }
    },
    "label": {
        "colours": {"dark_bg": "#00000000", "normal_text": "#c3c2b7"},
        "misc": {"text_horiz_alignment": "left"},
    },
    "#value": {
        "colours": {"normal_text": "#ffffff"},
        "misc": {"text_horiz_alignment": "right"},
    },
    "#section": {
        "colours": {"normal_text": "#ffffff"},
        "font": {"name": "noto_sans", "size": "15", "bold": "1"},
    },
    "#note": {"colours": {"normal_text": "#8c8b83"}},
}
