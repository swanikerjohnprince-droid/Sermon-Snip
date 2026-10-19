import array
import math
import sys
import wave

PHRASES = [
    "remember", "listen", "behold", "never", "always", "today", "right now",
    "i declare", "i decree", "the truth", "listen to me", "don't give up",
    "do not give up", "jesus said", "the bible says", "the word of god",
    "breakthrough", "victory", "faith", "promise", "power", "glory",
    "salvation", "holy spirit", "kingdom", "miracle", "purpose",
    "hallelujah", "amen", "somebody", "shout", "say it", "can i tell you",
    "are you hearing me"
]

def read_pcm_wav(path):
    """Read PCM WAV into compact float array, avoiding huge Python sample lists."""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.getnframes()
        if wf.getcomptype() != "NONE":
            raise ValueError("Please use uncompressed PCM WAV audio.")
        if width != 2:
            raise ValueError(
                f"Expected 16-bit PCM WAV, but this file uses {width * 8}-bit samples. "
                "Export/convert an analysis copy to 16-bit PCM WAV."
            )
        # Read in bounded chunks and downmix to mono while reading.
        samples = array.array("f")
        chunk_frames = max(1, rate * 30)
        while True:
            raw = wf.readframes(chunk_frames)
            if not raw:
                break
            pcm = array.array("h")
            pcm.frombytes(raw)
            if sys.byteorder != "little":
                pcm.byteswap()
            if channels == 1:
                samples.extend(v / 32768.0 for v in pcm)
            else:
                for i in range(0, len(pcm) - channels + 1, channels):
                    samples.append(sum(pcm[i:i + channels]) / (channels * 32768.0))
        return rate, samples

def energy_windows(samples, rate, seconds=1):
    """Compute RMS in one-second windows without allocating large temporary lists."""
    size = max(1, int(rate * seconds))
    rms = []
    for start in range(0, len(samples), size):
        stop = min(start + size, len(samples))
        total = 0.0
        for i in range(start, stop):
            v = samples[i]
            total += v * v
        count = stop - start
        if count:
            rms.append(math.sqrt(total / count))
    if not rms:
        return []
    ordered = sorted(rms)
    baseline = max(ordered[int(.55 * (len(ordered) - 1))], .008)
    scores = [min(1.0, max(0.0, (x / baseline - .65) / 2.4)) for x in rms]
    for i in range(1, len(scores)):
        rise = max(0.0, rms[i] - rms[i - 1]) / baseline
        scores[i] = min(1.0, scores[i] + min(.22, rise * .08))
    return scores

def transcribe(path, model_name="base", progress=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is missing. Run INSTALL_AND_RUN.bat.") from exc
    if progress:
        progress("Loading Whisper model (first run may download it)…")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(path), word_timestamps=False, vad_filter=True)
    rows = []
    for seg in segments:
        rows.append({"start": float(seg.start), "end": float(seg.end), "text": seg.text.strip()})
    if not rows:
        raise RuntimeError("No speech detected in this recording.")
    return rows, getattr(info, "language", "unknown")

def text_score(text):
    low = text.lower()
    hits = [phrase for phrase in PHRASES if phrase in low]
    score = min(1.0, len(hits) * .13 + (.12 if "!" in text else 0) + (.06 if "?" in text else 0))
    if any(low.startswith(prefix) for prefix in ("but ", "because ", "when ", "if ", "you ", "god ", "jesus ")):
        score = min(1.0, score + .08)
    return score, hits[:5]

def candidates(transcript, energy, duration, limit=30):
    groups, current = [], []
    for item in transcript:
        if not current:
            current = [item]
        elif item["end"] - current[0]["start"] <= 28 and item["start"] - current[-1]["end"] < 2.8:
            current.append(item)
        else:
            groups.append(current)
            current = [item]
    if current:
        groups.append(current)
    results = []
    for group in groups:
        start = max(0.0, group[0]["start"] - 1.0)
        end = min(duration, group[-1]["end"] + 1.5)
        text = " ".join(x["text"] for x in group).strip()
        if end - start < 4 or len(text.split()) < 5:
            continue
        lo, hi = int(start), min(len(energy), max(int(start) + 1, math.ceil(end)))
        vals = energy[lo:hi]
        audio = sum(vals) / len(vals) if vals else 0.0
        peak = max(vals) if vals else 0.0
        spoken, hits = text_score(text)
        score = 100 * (.40 * audio + .45 * spoken + .15 * peak)
        results.append({
            "start": round(start, 2), "end": round(end, 2), "score": round(score, 1),
            "audio_score": round(audio, 3), "text_score": round(spoken, 3),
            "peak_score": round(peak, 3), "text": text, "signals": hits
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    chosen = []
    for item in results:
        if all(item["end"] <= old["start"] or item["start"] >= old["end"] for old in chosen):
            chosen.append(item)
        if len(chosen) >= limit:
            break
    return sorted(chosen, key=lambda item: item["start"])
