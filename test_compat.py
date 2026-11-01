import fairy
from PySide6.QtWidgets import QApplication

app = QApplication([])

print("run_command:", fairy.run_command_impl("echo cross-platform-ok"))
print("close_app missing:", fairy.close_app_impl("no_such_app_xyz123"))
print("open_app missing:", fairy.open_app_impl("definitely_not_an_app_xyz")[:60])
print("find_hermes:", fairy.find_hermes())
print("find_terminal:", fairy.find_terminal())
print("konsole argv:", fairy.term_launch("/usr/bin/konsole", "T",
      ["/x/hermes", "chat", "-q", "has -q inside"]))
print("gnome argv:", fairy.term_launch("/usr/bin/gnome-terminal", "T",
      ["/x/hermes", "chat", "-q", "seed text"]))

# full handoff through the NEW code path
b = fairy.ToolBrain()
r = b.reply("say exactly: TEST HANDOFF")
print("chat roundtrip:", r[:40])
res = b._open_hermes_session("compat test")
print("handoff tool says:", res)
