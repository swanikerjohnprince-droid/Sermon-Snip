import re
import subprocess

def probe_duration(path):
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True
        )
        return float(proc.stdout.strip())
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe not found. Install FFmpeg and add its bin folder to PATH.") from exc
    except Exception as exc:
        raise RuntimeError("Could not read video duration; check FFmpeg and the file.") from exc

def detect_cuts(path, threshold=0.32):
    cmd = ["ffmpeg", "-hide_banner", "-i", str(path), "-vf",
           f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg not found. Install FFmpeg and add its bin folder to PATH.") from exc
    times = []
    for line in proc.stderr.splitlines():
        if "showinfo" in line and "pts_time:" in line:
            match = re.search(r"pts_time:\s*([0-9.]+)", line)
            if match:
                time = float(match.group(1))
                if not times or time - times[-1] > .15:
                    times.append(round(time, 3))
    if proc.returncode and not times:
        raise RuntimeError("FFmpeg scene detection failed:\n" + "\n".join(proc.stderr.splitlines()[-10:]))
    return times

def make_scenes(cuts, duration):
    points = sorted(set([0.0] + [t for t in cuts if .1 < t < duration - .1] + [float(duration)]))
    return [{"scene": i + 1, "start": round(points[i], 3), "end": round(points[i + 1], 3),
             "duration": round(points[i + 1] - points[i], 3)} for i in range(len(points) - 1)]
