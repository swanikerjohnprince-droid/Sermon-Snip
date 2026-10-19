# Sermon-Snip

AI-assisted sermon highlight finder for Windows and DaVinci Resolve 21 Free.

## Current prototype
- Transcribes an uncompressed PCM WAV with faster-whisper.
- Ranks candidate highlights using transcript phrase signals and audio energy.
- Builds excerpts around roughly 60 seconds, preferring sentence-ending boundaries to preserve complete thoughts; shorter impactful clips can still rank.
- Sorts results from highest score to lowest and shows the full transcript excerpt in a hover preview.
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
Audio-energy analysis now reads the WAV in 10-second chunks and stores only one score per analysis window. Whisper transcription also reads and transcribes 30-second chunks instead of decoding the entire recording into memory. This is designed to avoid the original full-file allocation that caused `MemoryError`. Input must be uncompressed 16-bit PCM WAV; your original media is not modified.

The repository includes unit tests for mono and stereo WAV analysis across chunk boundaries. GitHub Actions runs them on pushes and pull requests.
