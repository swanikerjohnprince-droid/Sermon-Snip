import math
import tempfile
import unittest
import wave
from pathlib import Path

from analyzer import analyze_wav_energy, candidates


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


class HighlightCandidateTests(unittest.TestCase):
    def test_candidates_include_complete_thought_metadata_and_sort_by_score(self):
        transcript = [
            {"start": 0.0, "end": 18.0, "text": "The Bible says we must keep our faith because God is faithful."},
            {"start": 18.2, "end": 37.0, "text": "Listen to me, the promise of God is greater than your problem."},
            {"start": 37.2, "end": 58.0, "text": "Do not give up, because victory comes through faith in Jesus Christ."},
            {"start": 58.2, "end": 75.0, "text": "Today we remember that the kingdom of God will never fail."},
            {"start": 75.2, "end": 95.0, "text": "So keep trusting the Lord, and let your life show his glory."},
        ]
        energy = [0.4 + (i % 4) * 0.1 for i in range(100)]
        results = candidates(transcript, energy, 100, limit=20)
        self.assertTrue(results)
        scores = [item["score"] for item in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all("complete_thought" in item for item in results))
        self.assertTrue(all(item["duration"] > 0 for item in results))
        self.assertTrue(all(item["text"].strip() for item in results))


if __name__ == "__main__":
    unittest.main()
