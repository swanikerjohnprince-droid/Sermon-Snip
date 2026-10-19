import math
import tempfile
import unittest
import wave
from pathlib import Path

from analyzer import analyze_wav_energy


class StreamingWavAnalysisTests(unittest.TestCase):
    def make_wav(self, path, channels=1, rate=8000, duration=10.5):
        frames = int(rate * duration)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            data = bytearray()
            for i in range(frames):
                # A non-silent, low-amplitude 220 Hz tone.
                sample = int(4000 * math.sin(2 * math.pi * 220 * i / rate))
                for _ in range(channels):
                    data.extend(sample.to_bytes(2, "little", signed=True))
            wf.writeframes(data)

    def test_longer_than_one_chunk_returns_per_second_scores(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "long_mono.wav"
            self.make_wav(path)
            duration, scores = analyze_wav_energy(path)
            self.assertAlmostEqual(duration, 10.5, places=2)
            self.assertEqual(len(scores), 11)
            self.assertTrue(all(0.0 <= score <= 1.0 for score in scores))
            self.assertTrue(any(score > 0 for score in scores))

    def test_stereo_wav_is_downmixed_without_full_audio_buffer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "stereo.wav"
            self.make_wav(path, channels=2, duration=2.25)
            duration, scores = analyze_wav_energy(path)
            self.assertAlmostEqual(duration, 2.25, places=2)
            self.assertEqual(len(scores), 3)
            self.assertTrue(any(score > 0 for score in scores))


if __name__ == "__main__":
    unittest.main()
