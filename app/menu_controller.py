# menu_controller.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

# A function that performs an action when a leaf item is selected.
Action = Callable[[], None]

@dataclass
class MenuItem:
    """A single menu node. Either a leaf with an action, or a parent with children."""
    label: str
    action: Optional[Action] = None
    children: List["MenuItem"] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return not self.children


class MenuController:
    """
    Tree + stack menu navigator.

    - Use move(+1/-1) to change the cursor in the current node.
    - Use select() to activate a leaf's action or descend into a submenu.
    - Use back() to go up one level.
    - Use get_render_data(max_lines) to obtain (title, visible_items) for drawing.
    """
    def __init__(self, root: MenuItem):
        if not isinstance(root, MenuItem):
            raise TypeError("root must be a MenuItem")
        # stack keeps (node, cursor_index)
        self._stack: List[Tuple[MenuItem, int]] = [(root, 0)]

    # ------------------------
    # Core navigation helpers
    # ------------------------
    @property
    def node(self) -> MenuItem:
        return self._stack[-1][0]

    @property
    def cursor(self) -> int:
        return self._stack[-1][1]

    def _set_cursor(self, idx: int) -> None:
        node, _ = self._stack[-1]
        self._stack[-1] = (node, idx)

    def move(self, delta: int) -> None:
        """Move selection up/down within current node's children."""
        items = self.node.children
        if not items:
            return
        count = len(items)
        new_idx = (self.cursor + delta) % count
        self._set_cursor(new_idx)

    def select(self) -> None:
        """If on a leaf, run its action; if on a parent, descend into it."""
        items = self.node.children
        if not items:
            return
        item = items[self.cursor]
        if item.is_leaf:
            if item.action:
                item.action()
        else:
            # Enter submenu with cursor reset to 0
            self._stack.append((item, 0))

    def back(self) -> None:
        """Go up one level if possible."""
        if len(self._stack) > 1:
            self._stack.pop()

    # ------------------------
    # Rendering utilities
    # ------------------------
    def breadcrumb(self, sep: str = " > ") -> str:
        """Return a breadcrumb like 'Main > Display'."""
        return sep.join(frame[0].label for frame in self._stack)

    def get_render_data(self, max_lines: int = 6) -> Tuple[str, List[Tuple[str, bool, bool]]]:
        """
        Prepare data for drawing.

        Returns:
            title: str                         (breadcrumb for convenience)
            visible: List of tuples:
                (label, is_selected, has_children)

        Scrolling is handled here if there are more items than max_lines.
        """
        title = self.breadcrumb()
        items = self.node.children or []
        cur = self.cursor

        # Compute window start for simple scroll-follow behavior
        start = 0
        if len(items) > max_lines and cur >= max_lines:
            start = cur - max_lines + 1

        window = items[start:start + max_lines]
        visible = [(it.label, (start + i) == cur, not it.is_leaf) for i, it in enumerate(window)]
        return title, visible

    # ------------------------
    # Convenience: event handler
    # ------------------------
    def handle_event(self, event: str) -> None:
        """
        Map simple string events to actions.
        Expected values: 'UP', 'DOWN', 'SELECT', 'BACK'
        """
        e = event.upper()
        if e == "UP":
            self.move(-1)
        elif e == "DOWN":
            self.move(+1)
        elif e == "SELECT":
            self.select()
        elif e == "BACK":
            self.back()

# ------------------------
# Example usage (console)
# ------------------------
if __name__ == "__main__":
    # Define some dummy actions
    def say(msg):
        return lambda: print(f"[ACTION] {msg}")

    # Build a tiny tree
    root = MenuItem("Main", children=[
        MenuItem("Display", children=[
            MenuItem("Backlight +", action=say("Backlight up")),
            MenuItem("Backlight -", action=say("Backlight down")),
            MenuItem("Rotate 0°",  action=say("Rotate 0")),
            MenuItem("Rotate 90°", action=say("Rotate 90")),
        ]),
        MenuItem("Patterns", children=[
            MenuItem("Rainbow",   action=say("Pattern: rainbow")),
            MenuItem("Solid Red", action=say("Pattern: red")),
        ]),
        MenuItem("System", children=[
            MenuItem("Reboot",   action=say("Rebooting...")),
            MenuItem("Shutdown", action=say("Shutting down...")),
        ]),
    ])

    menu = MenuController(root)