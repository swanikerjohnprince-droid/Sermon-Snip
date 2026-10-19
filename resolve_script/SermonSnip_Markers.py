# Run from DaVinci Resolve's Workspace > Scripts menu.
# Add markers from a Sermon-Snip JSON export to the currently selected timeline.
import json
import tkinter as tk
from tkinter import filedialog, messagebox

def main():
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title="Choose Sermon-Snip highlight JSON",
                                      filetypes=[("JSON", "*.json")])
    root.destroy()
    if not path:
        return
    with open(path, "r", encoding="utf-8") as stream:
        data = json.load(stream)
    try:
        project = resolve.GetProjectManager().GetCurrentProject()
        timeline = project.GetCurrentTimeline() if project else None
    except Exception:
        timeline = None
    if not timeline:
        messagebox.showerror("Sermon-Snip", "Open a project and select a timeline first.")
        return
    try:
        fps = float(timeline.GetSetting("timelineFrameRate"))
    except Exception:
        fps = 24.0
    count = 0
    for highlight in data.get("highlights", []):
        frame = max(0, int(round(float(highlight.get("start", 0)) * fps)))
        duration = max(1, int(round((float(highlight.get("end", 0)) -
                                     float(highlight.get("start", 0))) * fps)))
        label = "Sermon-Snip " + str(highlight.get("score", ""))
        note = str(highlight.get("text", ""))[:900]
        try:
            ok = timeline.AddMarker(frame, "Cyan", label, note, duration, "Sermon-Snip")
        except Exception:
            try:
                ok = timeline.AddMarker(frame, "Cyan", label, note, duration)
            except Exception:
                ok = False
        if ok:
            count += 1
    messagebox.showinfo("Sermon-Snip", f"Added {count} markers. Verify audio/timeline offsets.")
if __name__ == "__main__":
    main()
