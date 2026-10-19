import csv
import json
import queue
import threading
import traceback
import wave
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from analyzer import analyze_wav_energy, transcribe, candidates
from scene_detect import probe_duration, detect_cuts, make_scenes

def stamp(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"

class App:
    def __init__(self, root):
        self.root = root
        root.title("Sermon-Snip — Sermon Highlight Finder")
        root.geometry("1050x740")
        root.minsize(820, 580)
        self.audio = None
        self.video = None
        self.results = []
        self.transcript = []
        self.events = queue.Queue()
        self.duration = 0
        self.language = "unknown"
        self.model = tk.StringVar(value="large-v3")
        self.vocabulary = tk.StringVar(value="")
        self.status = tk.StringVar(value="Choose a sermon WAV to begin.")
        self.build_ui()
        root.after(150, self.poll)

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#10141b")
        style.configure("TLabel", background="#10141b", foreground="#e9eef5")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground="#ffffff")
        style.configure("Sub.TLabel", foreground="#aeb9c8")
        style.configure("Treeview", rowheight=32, background="#171e28", foreground="#e9eef5",
                        fieldbackground="#171e28")
        style.configure("Treeview.Heading", background="#273241", foreground="#ffffff")
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Sermon-Snip", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Find sermon highlights • detect camera cuts • prepare vertical edits",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 12))
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=4)
        ttk.Button(bar, text="Choose sermon audio (PCM WAV)", command=self.choose_audio).pack(side="left")
        ttk.Button(bar, text="Choose video for scene cuts", command=self.choose_video).pack(side="left", padx=6)
        ttk.Label(bar, text="Model").pack(side="left", padx=(8, 3))
        ttk.Combobox(bar, textvariable=self.model,
                     values=["medium", "distil-large-v3", "large-v3"],
                     width=17, state="readonly").pack(side="left")
        ttk.Label(bar, text="Sermon vocabulary (optional)").pack(side="left", padx=(8, 3))
        ttk.Entry(bar, textvariable=self.vocabulary, width=28).pack(side="left")
        ttk.Button(bar, text="Analyze audio", command=self.analyze).pack(side="left", padx=6)
        ttk.Button(bar, text="Detect cuts", command=self.detect).pack(side="left")
        self.audio_label = ttk.Label(outer, text="Audio: none", style="Sub.TLabel")
        self.audio_label.pack(anchor="w", pady=2)
        self.video_label = ttk.Label(outer, text="Video: none", style="Sub.TLabel")
        self.video_label.pack(anchor="w", pady=2)
        ttk.Label(outer, text="Candidate highlights — highest score first; hover over an excerpt to read it all",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(12, 5))
        self.tree = ttk.Treeview(outer, columns=("score", "start", "end", "text"), show="headings")
        for col, label, width in [("score", "Score", 65), ("start", "Start", 80),
                                  ("end", "End", 80), ("text", "Transcript excerpt", 700)]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w" if col == "text" else "center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.detail)
        row = ttk.Frame(outer)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="Export highlights JSON", command=self.export_json).pack(side="left")
        ttk.Button(row, text="Export highlights CSV", command=self.export_csv).pack(side="left", padx=8)
        self.tree.bind("<Motion>", self.show_excerpt_tooltip)
        self.tree.bind("<Leave>", self.hide_excerpt_tooltip)
        self.tooltip = None
        self.tooltip_row = None
        self.details = tk.Text(outer, height=4, wrap="word", bg="#171e28", fg="#e9eef5",
                               relief="flat", padx=8, pady=6)
        self.details.pack(fill="x")
        self.details.insert("1.0", "Select a result to inspect transcript and scoring signals.")
        self.details.configure(state="disabled")
        ttk.Label(outer, textvariable=self.status, style="Sub.TLabel").pack(anchor="w", pady=(7, 0))

    def show_excerpt_tooltip(self, event):
        # Show the complete transcript excerpt when hovering over its table cell.
        row_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not row_id or column != "#4":
            self.hide_excerpt_tooltip()
            return
        if row_id == self.tooltip_row:
            return
        self.hide_excerpt_tooltip()
        try:
            excerpt = self.tree.set(row_id, "text")
            if not excerpt:
                return
            popup = tk.Toplevel(self.root)
            popup.wm_overrideredirect(True)
            popup.attributes("-topmost", True)
            x = min(event.x_root + 18, self.root.winfo_screenwidth() - 600)
            y = min(event.y_root + 18, self.root.winfo_screenheight() - 300)
            popup.geometry(f"+{max(0, x)}+{max(0, y)}")
            frame = tk.Frame(popup, bg="#202a38", bd=1, relief="solid")
            frame.pack(fill="both", expand=True)
            tk.Label(
                frame, text="FULL EXCERPT", anchor="w",
                bg="#202a38", fg="#9fc5ff", font=("Segoe UI", 9, "bold"),
                padx=10, pady=6
            ).pack(fill="x")
            body = tk.Text(
                frame, wrap="word", width=72, height=12,
                bg="#171e28", fg="#e9eef5", relief="flat",
                padx=10, pady=8, font=("Segoe UI", 10)
            )
            scroll = ttk.Scrollbar(frame, orient="vertical", command=body.yview)
            body.configure(yscrollcommand=scroll.set)
            body.insert("1.0", excerpt)
            body.configure(state="disabled")
            body.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            self.tooltip = popup
            self.tooltip_row = row_id
        except tk.TclError:
            self.tooltip = None
            self.tooltip_row = None

    def hide_excerpt_tooltip(self, _event=None):
        if self.tooltip is not None:
            try:
                self.tooltip.destroy()
            except tk.TclError:
                pass
        self.tooltip = None
        self.tooltip_row = None

    def choose_audio(self):
        path = filedialog.askopenfilename(filetypes=[("WAV audio", "*.wav")])
        if path:
            self.audio = Path(path)
            self.audio_label.config(text="Audio: " + path)

    def choose_video(self):
        path = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mov *.mkv *.mxf *.avi"),
                                                     ("All files", "*.*")])
        if path:
            self.video = Path(path)
            self.video_label.config(text="Video: " + path)

    def analyze(self):
        if not self.audio:
            messagebox.showinfo("Choose audio", "Choose an uncompressed PCM WAV first.")
            return
        try:
            with wave.open(str(self.audio), "rb") as wf:
                if wf.getcomptype() != "NONE":
                    raise ValueError("WAV is compressed")
                if wf.getsampwidth() != 2:
                    raise ValueError("WAV is not 16-bit PCM")
        except Exception as exc:
            messagebox.showerror("Audio format", f"Please use uncompressed 16-bit PCM WAV.\n\n{exc}")
            return
        self.status.set("Analyzing audio and transcribing…")
        threading.Thread(
            target=self.worker,
            args=(self.model.get(), self.vocabulary.get().strip()),
            daemon=True,
        ).start()

    def worker(self, model_name="large-v3", vocabulary=""):
        try:
            duration, energy = analyze_wav_energy(
                self.audio,
                progress=lambda fraction: self.events.put(
                    ("status", f"Analyzing audio energy… {fraction:.0%}")
                ),
            )
            transcript, language = transcribe(
                self.audio,
                model_name,
                progress=lambda message: self.events.put(("status", message)),
                language="en",
                device="auto",
                chunk_seconds=30,
                overlap_seconds=2,
                initial_prompt=vocabulary or None,
            )
            results = candidates(transcript, energy, duration)
            self.events.put(("done", (results, transcript, language, duration)))
        except Exception as exc:
            details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            try:
                with (Path(__file__).resolve().parent / "sermon_snip_error.log").open("a", encoding="utf-8") as log:
                    log.write("\n" + "=" * 70 + "\nAUDIO ANALYSIS ERROR\n" + details + "\n")
            except Exception:
                pass
            self.events.put(("error", f"{type(exc).__name__}: {exc!r}\n\nFull traceback saved to sermon_snip_error.log.\n\n{details}"))

    def detect(self):
        if not self.video:
            messagebox.showinfo("Choose video", "Choose a video first.")
            return
        self.status.set("Detecting likely visual cuts with FFmpeg…")
        threading.Thread(target=self.scene_worker, daemon=True).start()

    def scene_worker(self):
        try:
            duration = probe_duration(self.video)
            cuts = detect_cuts(self.video)
            scenes = make_scenes(cuts, duration)
            self.events.put(("scenes", (duration, cuts, scenes)))
        except Exception as exc:
            self.events.put(("error", f"{type(exc).__name__}: {exc!r}"))

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "status":
                    self.status.set(data)
                elif kind == "error":
                    self.status.set("Task failed — see error details.")
                    messagebox.showerror("Sermon-Snip — detailed error", data if data.strip() else "Unknown error.")
                elif kind == "done":
                    self.results, self.transcript, self.language, self.duration = data
                    # Keep the highest-scoring excerpt at the top of the list.
                    self.results.sort(key=lambda item: item.get("score", 0), reverse=True)
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    for i, result in enumerate(self.results):
                        self.tree.insert("", "end", iid=str(i), values=(
                            result["score"], stamp(result["start"]), stamp(result["end"]), result["text"]))
                    self.status.set(f"Analysis complete: {len(self.results)} candidates; language {self.language}.")
                elif kind == "scenes":
                    duration, cuts, scenes = data
                    output = filedialog.asksaveasfilename(defaultextension=".json",
                        initialfile="sermon_snip_scenes.json", filetypes=[("JSON", "*.json")])
                    if output:
                        Path(output).write_text(json.dumps({
                            "app": "Sermon-Snip", "version": "0.3",
                            "source_video": str(self.video), "duration_seconds": duration,
                            "scene_cut_threshold": .32, "cut_times_seconds": cuts, "scenes": scenes,
                            "note": "Scene detection only; subject tracking and rendering are not yet included."
                        }, indent=2), encoding="utf-8")
                        self.status.set(f"Detected {len(cuts)} cuts across {len(scenes)} scenes. Report saved.")
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def detail(self, _=None):
        selection = self.tree.selection()
        if not selection:
            return
        result = self.results[int(selection[0])]
        text = (f"Score {result['score']}/100 | Audio {result['audio_score']:.2f} | "
                f"Text {result['text_score']:.2f} | Peak {result['peak_score']:.2f}\n"
                f"Signals: {', '.join(result['signals']) or 'No configured phrase signals'}\n\n{result['text']}")
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def export_json(self):
        if not self.results:
            messagebox.showinfo("No results", "Analyze audio first.")
            return
        output = filedialog.asksaveasfilename(defaultextension=".json",
            initialfile="sermon_snip_highlights.json", filetypes=[("JSON", "*.json")])
        if output:
            Path(output).write_text(json.dumps({
                "app": "Sermon-Snip", "version": "0.3", "source_audio": str(self.audio),
                "duration_seconds": self.duration, "language": self.language,
                "timing_note": "Times are relative to source audio start. Verify offsets in Resolve.",
                "highlights": self.results
            }, indent=2, ensure_ascii=False), encoding="utf-8")
            self.status.set("Exported " + output)

    def export_csv(self):
        if not self.results:
            messagebox.showinfo("No results", "Analyze audio first.")
            return
        output = filedialog.asksaveasfilename(defaultextension=".csv",
            initialfile="sermon_snip_highlights.csv", filetypes=[("CSV", "*.csv")])
        if output:
            with open(output, "w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "start", "end", "score", "audio_score", "text_score", "peak_score", "signals", "text"])
                writer.writeheader()
                for item in self.results:
                    row = dict(item)
                    row["signals"] = "; ".join(item["signals"])
                    writer.writerow(row)
            self.status.set("Exported " + output)

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
