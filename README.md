# Sermon-Snip

AI-assisted sermon highlight finder for Windows and DaVinci Resolve 21 Free.

## Current prototype
- Transcribes an uncompressed PCM WAV with faster-whisper.
- Ranks candidate highlights using transcript phrase signals and audio energy.
- Uses compact audio arrays to avoid the original Python-list MemoryError.
- Optionally detects likely visual cuts with FFmpeg.
- Exports JSON/CSV and includes a DaVinci Resolve script to add timeline markers.

## Install
1. Install 64-bit Python 3.11 or 3.12 (recommended).
2. Run `INSTALL_AND_RUN.bat`.
3. Choose a PCM WAV and click **Analyze audio**. First run downloads the Whisper model.
4. For scene cuts, install FFmpeg and ensure `ffmpeg` and `ffprobe` are on PATH.

## Known limitations
- This is a companion desktop app, not a docked native Resolve panel.
- Automatic subject tracking, 9:16 reframing, and AutoSubs triggering are not implemented yet.
- Highlight scores are heuristic suggestions; review clips manually.
- Timeline marker times assume the source audio starts at timeline time zero.

## MemoryError fix
The WAV reader uses `array.array` rather than a Python list of millions of float objects. For extremely long/high-rate stereo files, create a mono 16-bit PCM WAV analysis copy. Keep your original media unchanged.
