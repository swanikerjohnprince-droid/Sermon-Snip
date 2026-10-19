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


def _score_rms(rms):
    """Convert per-window RMS values into normalized excitement scores."""
    if not rms:
        return []
    ordered = sorted(rms)
    baseline = max(ordered[int(.55 * (len(ordered) - 1))], .008)
    scores = [min(1.0, max(0.0, (x / baseline - .65) / 2.4)) for x in rms]
    for i in range(1, len(scores)):
        rise = max(0.0, rms[i] - rms[i - 1]) / baseline
        scores[i] = min(1.0, scores[i] + min(.22, rise * .08))
    return scores


def analyze_wav_energy(path, seconds=1, progress=None):
    """Analyze PCM WAV in bounded-memory chunks; never retain the full waveform.

    Memory use is proportional to the chunk size plus one RMS value per output
    window, rather than to the total number of audio samples.
    """
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        frames_total = wf.getnframes()
        if wf.getcomptype() != "NONE":
            raise ValueError("Please use uncompressed PCM WAV audio.")
        if width != 2:
            raise ValueError(
                f"Expected 16-bit PCM WAV, but this file uses {width * 8}-bit samples. "
                "Export/convert an analysis copy to 16-bit PCM WAV."
            )
        if channels < 1 or rate < 1:
            raise ValueError("The WAV file has invalid channel or sample-rate metadata.")

        window_frames = max(1, int(rate * seconds))
        chunk_frames = max(1, rate * 10)
        rms = []
        sum_squares = 0.0
        frames_in_window = 0
        frames_read = 0

        while True:
            raw = wf.readframes(chunk_frames)
            if not raw:
                break
            pcm = array.array("h")
            pcm.frombytes(raw)
            if sys.byteorder != "little":
                pcm.byteswap()
            frame_count = len(pcm) // channels
            if frame_count == 0:
                continue

            # Process one audio frame at a time; do not create per-frame slices.
            for frame in range(frame_count):
                base = frame * channels
                total = 0
                for channel in range(channels):
                    total += pcm[base + channel]
                mono = total / (channels * 32768.0)
                sum_squares += mono * mono
                frames_in_window += 1
                frames_read += 1
                if frames_in_window >= window_frames:
                    rms.append(math.sqrt(sum_squares / frames_in_window))
                    sum_squares = 0.0
                    frames_in_window = 0

            if progress and frames_total:
                progress(min(1.0, frames_read / frames_total))

        if frames_in_window:
            rms.append(math.sqrt(sum_squares / frames_in_window))

        duration = frames_total / rate
        return duration, _score_rms(rms)


def read_pcm_wav(path):
    """Compatibility helper: load mono WAV into a compact array.

    The app's main analysis path uses analyze_wav_energy() instead, which is
    bounded-memory and should be preferred for long recordings.
    """
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        if wf.getcomptype() != "NONE":
            raise ValueError("Please use uncompressed PCM WAV audio.")
        if width != 2:
            raise ValueError(
                f"Expected 16-bit PCM WAV, but this file uses {width * 8}-bit samples. "
                "Export/convert an analysis copy to 16-bit PCM WAV."
            )
        samples = array.array("f")
        chunk_frames = max(1, rate * 10)
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
                    total = 0
                    for channel in range(channels):
                        total += pcm[i + channel]
                    samples.append(total / (channels * 32768.0))
        return rate, samples


def energy_windows(samples, rate, seconds=1):
    """Compute RMS windows for an already-loaded mono sample array."""
    size = max(1, int(rate * seconds))
    rms = []
    for start in range(0, len(samples), size):
        stop = min(start + size, len(samples))
        total = 0.0
        for i in range(start, stop):
            value = samples[i]
            total += value * value
        count = stop - start
        if count:
            rms.append(math.sqrt(total / count))
    return _score_rms(rms)


def transcribe(path, model_name="base", progress=None):
    """Transcribe PCM WAV in 30-second chunks to keep memory bounded."""
    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper and its NumPy dependency are required. Run INSTALL_AND_RUN.bat.") from exc

    with wave.open(str(path), "rb") as wf:
        if wf.getcomptype() != "NONE" or wf.getsampwidth() != 2:
            raise ValueError("Transcription requires uncompressed 16-bit PCM WAV audio.")
        channels = wf.getnchannels()
        rate = wf.getframerate()
        total_frames = wf.getnframes()
        if channels < 1 or rate < 1:
            raise ValueError("The WAV file has invalid channel or sample-rate metadata.")
        chunk_frames = max(1, rate * 30)

    if progress:
        progress("Loading Whisper model (first run may download it)…")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    rows = []
    language = "unknown"
    processed_frames = 0

    with wave.open(str(path), "rb") as wf:
        while True:
            raw = wf.readframes(chunk_frames)
            if not raw:
                break
            pcm = np.frombuffer(raw, dtype="<i2")
            frame_count = len(pcm) // channels
            if frame_count == 0:
                continue
            mono = pcm[:frame_count * channels].reshape(frame_count, channels).mean(axis=1)
            audio = (mono.astype(np.float32, copy=False) / 32768.0)
            chunk_start = processed_frames / rate
            segments, info = model.transcribe(audio, word_timestamps=False, vad_filter=True)
            if language == "unknown":
                language = getattr(info, "language", "unknown")
            for seg in segments:
                rows.append({
                    "start": round(chunk_start + float(seg.start), 3),
                    "end": round(chunk_start + float(seg.end), 3),
                    "text": seg.text.strip(),
                })
            processed_frames += frame_count
            if progress and total_frames:
                progress(f"Transcribing sermon… {min(1.0, processed_frames / total_frames):.0%}")

    if not rows:
        raise RuntimeError("No speech detected in this recording.")
    return rows, language


def text_score(text):
    low = text.lower()
    hits = [phrase for phrase in PHRASES if phrase in low]
    score = min(1.0, len(hits) * .13 + (.12 if "!" in text else 0) + (.06 if "?" in text else 0))
    if any(low.startswith(prefix) for prefix in ("but ", "because ", "when ", "if ", "you ", "god ", "jesus ")):
        score = min(1.0, score + .08)
    return score, hits[:5]


def _ends_sentence(text):
    """Whether transcript text appears to end a complete sentence/thought."""
    return bool(text.rstrip().endswith((".", "!", "?", "…", '"', "”")))


def candidates(transcript, energy, duration, limit=30, target_seconds=60):
    """Find impactful excerpts near a minute, preferring complete sentence boundaries.

    The transcript model does not provide true semantic discourse boundaries, so
    punctuation and pauses are used as practical boundary signals. Shorter clips
    remain eligible when they score strongly.
    """
    if not transcript:
        return []

    # Start candidate windows at sentence boundaries, while tolerating ASR segments
    # that omit punctuation. A long pause is also a reasonable boundary.
    starts = []
    for i, item in enumerate(transcript):
        if i == 0:
            starts.append(i)
            continue
        previous = transcript[i - 1]
        gap = item["start"] - previous["end"]
        if _ends_sentence(previous["text"]) or gap >= 1.0:
            starts.append(i)

    raw_results = []
    seen_ranges = set()
    min_seconds = 12.0
    max_seconds = 82.0

    for first in starts:
        start_time = max(0.0, float(transcript[first]["start"]) - 0.5)
        best = None
        for last in range(first, len(transcript)):
            item = transcript[last]
            if last > first and item["start"] - transcript[last - 1]["end"] >= 2.8:
                break
            end_time = min(duration, float(item["end"]) + 0.5)
            length = end_time - start_time
            if length > max_seconds:
                break
            if length < min_seconds:
                continue

            # Prefer thought-ending punctuation. Near the target, allow the
            # nearest segment boundary if Whisper omitted punctuation.
            sentence_end = _ends_sentence(item["text"])
            if not sentence_end and abs(length - target_seconds) > 8:
                continue

            text = " ".join(x["text"].strip() for x in transcript[first:last + 1]).strip()
            if len(text.split()) < 12:
                continue
            # Penalize windows that are far from the target, but allow genuinely
            # short, punchy excerpts to remain competitive.
            duration_fit = max(0.45, 1.0 - abs(length - target_seconds) / target_seconds)
            lo = max(0, int(start_time))
            hi = min(len(energy), max(lo + 1, math.ceil(end_time)))
            vals = energy[lo:hi]
            audio = sum(vals) / len(vals) if vals else 0.0
            peak = max(vals) if vals else 0.0
            spoken, hits = text_score(text)
            completeness = 1.0 if sentence_end else 0.78
            score = 100 * (.36 * audio + .42 * spoken + .14 * peak + .08 * duration_fit)
            score *= completeness
            key = (round(start_time), round(end_time))
            if key in seen_ranges:
                continue
            result = {
                "start": round(start_time, 2), "end": round(end_time, 2),
                "duration": round(length, 1), "score": round(score, 1),
                "audio_score": round(audio, 3), "text_score": round(spoken, 3),
                "peak_score": round(peak, 3), "text": text, "signals": hits,
                "complete_thought": sentence_end,
            }
            # Keep the strongest candidate for each start boundary, favoring
            # a complete ending and proximity to about one minute.
            rank = score + (5 if sentence_end else 0) - abs(length - target_seconds) * 0.04
            if best is None or rank > best[0]:
                best = (rank, result, key)
            # Once we're well beyond target, don't keep expanding this excerpt.
            if length >= target_seconds + 10 and sentence_end:
                break
        if best:
            seen_ranges.add(best[2])
            raw_results.append(best[1])

    # Rank candidates by score (highest first), while reducing near-duplicates.
    raw_results.sort(key=lambda item: item["score"], reverse=True)
    chosen = []
    for item in raw_results:
        if all(
            item["end"] <= old["start"] or item["start"] >= old["end"]
            or (abs(item["start"] - old["start"]) < 8 and abs(item["end"] - old["end"]) < 15)
            for old in chosen
        ):
            chosen.append(item)
        if len(chosen) >= limit:
            break
    return chosen
