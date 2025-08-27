# app/ui_render.py
from typing import Dict, Any
from PIL import Image, ImageDraw, ImageFont

def load_font(size=20):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()

def render_menu(canvas, view, status, theme):
    W, H = canvas.size
    d = ImageDraw.Draw(canvas)
    fg = theme.get("fg", "white")
    bg = theme.get("bg", "black")
    accent = theme.get("accent", "cyan")

    d.rectangle((0, 0, W, H), fill=bg)

    font_small = load_font(14)
    bar_h = 20
    d.rectangle((0, 0, W, bar_h), fill="#101010")
    d.text((6, 2), status.get("time", ""), fill=fg, font=font_small)
    right_info = status.get("wifi", "")
    if isinstance(right_info, str):
        items = [(right_info, fg)] if right_info else []
    else:
        items = [(txt, col or fg) for txt, col in right_info]
    x = W - 6
    for txt, col in reversed(items):
        tw = d.textlength(txt, font=font_small)
        x -= tw
        d.text((x, 2), txt, fill=col, font=font_small)
        x -= 6
    d.line((0, bar_h, W, bar_h), fill="#404040")

    font_title = load_font(20)
    d.text((8, bar_h + 6), view.get("title",""), fill=accent, font=font_title)

    font_row = load_font(18)
    font_row_stub = load_font(18)  # same face; use a dimmer color
    row_y = bar_h + 34
    row_h = 26
    padding = 8

    # Determine how many rows fit on the screen and which slice of items to draw
    items = view.get("items", [])
    max_rows = max(1, (H - row_y) // row_h)
    focus_idx = next((i for i, it in enumerate(items) if it.get("focused")), 0)
    top_idx = max(0, min(focus_idx - max_rows + 1, len(items) - max_rows))
    visible = items[top_idx : top_idx + max_rows]

    for item in visible:
        label = item.get("label","")
        value = item.get("value","")
        focused = item.get("focused", False)
        live = item.get("live", True)
        needs_restart = item.get("restart", False)

        if not live:
            label_disp = f"{label} (stub)"
            color = "#808080"
        else:
            label_disp = label
            color = fg

        if needs_restart:
            # append a small indicator to the value or label
            value = (value + "  ↻") if value else "↻"

        if focused:
            d.rectangle((4, row_y - 2, W - 4, row_y + row_h - 2), outline=accent, width=2)

        d.text((padding + 6, row_y), label_disp, fill=color, font=font_row)
        if value:
            tw = d.textlength(value, font=font_row)
            d.text((W - padding - 6 - tw, row_y), value, fill=color, font=font_row)
        row_y += row_h

