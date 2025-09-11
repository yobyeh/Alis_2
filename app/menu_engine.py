# app/menu_engine.py
# Data-driven menu controller for Alis
# - Consumes a JSON menu spec (menu.json)
# - Edits a settings dict in-place (settings.json persisted via save_cb)
# - Produces a view-model dict for the renderer (title + list of items)
# - Handles navigation with events: "UP", "DOWN", "SELECT", "BACK"
#
# Notes:
# - Some settings are "live" (take effect immediately).
# - Some settings require a restart (e.g., display.rotation).
#   When such a binding changes, we set settings.system.restart_required = True
#   and the UI can show an indicator (↻).
#
# The renderer is intentionally separate (see app/ui_render.py).

from __future__ import annotations
import time
from typing import Any, Dict, List, Callable, Optional

Event = str  # "UP" | "DOWN" | "SELECT" | "BACK"

# Which bindings actually change behavior RIGHT NOW
LIVE_BINDINGS = {
    "display.brightness",
    "display.sleep_seconds",
    "display.screensaver_enabled",
    "led.brightness",
    # Wire more here as you implement them
}

# Which bindings require a restart to take effect
RESTART_BINDINGS = {
    "display.rotation",
    # Add more if needed later
}


class MenuController:
    """
    Pure-logic menu controller:
      - Holds the current screen id and focus index
      - Applies edits to settings (toggle/number/select)
      - Exposes a view() dict for the renderer
      - Tracks last_input_ts for sleep/screensaver
    """

    def __init__(
        self,
        menu_spec: Dict[str, Any],
        settings: Dict[str, Any],
        save_cb: Callable[[Dict[str, Any]], None],
        action_cb: Optional[Callable[[str], None]] = None,
    ):
        self.spec = menu_spec
        self.settings = settings
        self.save_cb = save_cb
        self.action_cb = action_cb
        self.stack: List[str] = [menu_spec.get("root", "home")]
        self.focus_idx: int = 0
        self.last_input_ts: float = time.time()

    # ------------------ Public API ------------------

    def on_event(self, ev: Event) -> None:
        """Handle navigation / activation events."""
        self.last_input_ts = time.time()
        screen = self.current_screen()
        items = self._resolved_items(screen.get("items", []))
        if ev == "UP":
            if items:
                self.focus_idx = (self.focus_idx - 1) % len(items)
        elif ev == "DOWN":
            if items:
                self.focus_idx = (self.focus_idx + 1) % len(items)
        elif ev == "BACK":
            if len(self.stack) > 1:
                self.stack.pop()
                self.focus_idx = 0
        elif ev == "SELECT":
            self._activate(items, self.focus_idx)

    def view(self) -> Dict[str, Any]:
        """Return a renderer-friendly dict with title + item rows."""
        s = self.current_screen()
        items = self._resolved_items(s.get("items", []))
        return {
            "title": s.get("title", ""),
            "items": [self._item_view(it, i == self.focus_idx) for i, it in enumerate(items)],
        }

    def current_screen_id(self) -> str:
        return self.stack[-1]

    def current_screen(self) -> Dict[str, Any]:
        return self.spec["screens"][self.current_screen_id()]

    # ------------------ Internal helpers ------------------

    def _activate(self, items: List[Dict[str, Any]], idx: int) -> None:
        if not items:
            return
        it = items[idx]
        t = it.get("type")
        if t == "screen-link":
            to = it.get("to")
            if to and to in self.spec.get("screens", {}):
                self.stack.append(to)
                self.focus_idx = 0
            return

        if t == "toggle":
            binding = it.get("binding")
            if not binding:
                return
            new_val = not bool(self._get_binding(binding, False))
            self._apply_binding(binding, new_val)
            return

        if t == "number":
            binding = it.get("binding")
            if not binding:
                return
            cur = int(self._get_binding(binding, 0))
            step = int(it.get("step", 1))
            mn = int(it.get("min", cur - step * 10))
            mx = int(it.get("max", cur + step * 10))
            new_val = max(mn, min(mx, cur + step))  # bump on SELECT
            self._apply_binding(binding, new_val)
            return

        if t == "select":
            binding = it.get("binding")
            if not binding:
                return
            opts = self._options(it)
            if not opts:
                return
            cur = self._get_binding(binding, opts[0])
            try:
                i = opts.index(cur)
            except ValueError:
                i = -1
            new_val = opts[(i + 1) % len(opts)]
            self._apply_binding(binding, new_val)
            return

        if t == "action":
            action = it.get("action")
            if self.action_cb and action:
                self.action_cb(action)
            else:
                # Fallback: log the requested action
                print(f"[Menu] action requested: {action}")
            return

        # info/group/unknown: no-op on SELECT

    def _apply_binding(self, binding: str, value: Any) -> None:
        """Write a value into the nested settings dict and persist (debounced)."""
        self._set_binding(binding, value)
        # Mark restart-needed if applicable
        if binding in RESTART_BINDINGS:
            sys = self.settings.setdefault("system", {})
            sys["restart_required"] = True
        # Persist (debounced by the provided callback)
        self.save_cb(self.settings)

    def _item_view(self, it: Dict[str, Any], focused: bool) -> Dict[str, Any]:
        """Produce a small dict per row for rendering."""
        t = it.get("type")
        label = it.get("label", "")

        live = True
        restart = False
        if "binding" in it:
            b = it["binding"]
            live = b in LIVE_BINDINGS
            restart = b in RESTART_BINDINGS

        # Value string shown on the right
        if t in ("group", "action"):
            value = ""
        elif t == "info" and "binding" in it:
            value = str(self._get_binding(it["binding"], ""))
        elif t == "info":
            value = ""
        elif t == "toggle":
            value = "ON" if self._get_binding(it["binding"], False) else "OFF"
        elif t == "number":
            value = str(self._get_binding(it["binding"], 0))
        elif t == "select":
            value = str(self._get_binding(it["binding"], ""))
        elif t == "screen-link":
            value = "›"
        else:
            value = ""

        return {
            "type": t,
            "label": label,
            "value": value,
            "focused": focused,
            "live": live,
            "restart": restart,
        }

    def _resolved_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Resolve dynamic fields like options_source before rendering/activation."""
        out: List[Dict[str, Any]] = []
        for it in items:
            if it.get("type") == "select" and "options_source" in it:
                tmp = dict(it)
                tmp["options"] = self._options(tmp)
                out.append(tmp)
            else:
                out.append(it)
        return out

    def _options(self, it: Dict[str, Any]) -> List[Any]:
        """Provide options for 'select' items either from spec or a dynamic source."""
        src = it.get("options_source")
        if src == "programs.list":
            # Placeholder until you wire real discovery:
            return ["Default", "Arcade", "Kiosk"]
        # Fallback to static options array
        return list(it.get("options", []))

    # -------------- Settings path helpers --------------

    def _get_binding(self, path: str, default: Any = None) -> Any:
        node: Any = self.settings
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def _set_binding(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node = self.settings
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
