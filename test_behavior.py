import time, random
from PySide6.QtWidgets import QApplication
import fairy

app = QApplication([])
class QuietBrain:
    def reply(self, t): return "hm"

w = fairy.FairyWidget(brain=QuietBrain())
w.icon_only = True
w.move(300, 300)
w.show()

# 1) quip path
w._say(fairy.IDLE_QUIPS[0])
for _ in range(40): w.tick()
w.grab().save("snap7/quip_bubble.png")
print("quip:", w.typing_full[:40], "| state:", w.state, "| bubble:", w._bubble_wanted(time.time()))

# 2) drift path
w.set_state("ONLINE"); w._conv_until = 0; w._demo_hold_until = 0
w._move_target = (w.x() + 80, w.y() - 18)
p0 = (w.x(), w.y())
for _ in range(120): w.tick()
print("drift:", p0, "->", (w.x(), w.y()), "target reached:", w._move_target is None)

# 3) move-quip path
w._conv_until = 0; w._move_target = None; w.set_state("ONLINE")
random.seed(7)
w.drag_off = (10, 10)          # fake a drag
w.mouseReleaseEvent(None)
print("move-quip fired:", w.state == "TALKING", "|", (w.typing_full[:45] if w.state=="TALKING" else "-"))

# 4) behavior gating: hovered fairy must not quip or drift
w.set_state("ONLINE"); w._conv_until = 0
w._mouse_on = True
w._next_quip = 0; w._next_move = 0
random.seed(1)
w._behavior_tick()
print("hover-gated (expect True):", w.state == "ONLINE" and w._move_target is None)
