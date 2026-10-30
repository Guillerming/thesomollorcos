import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from tools import audio, edl, render, voice
from tools.synth import SR

VOICES = {"Mayoneso": voice.Voice("Mayoneso", "Mayoneso")}


class LoadVoicesTest(unittest.TestCase):
    def test_skips_info_keys_and_defaults_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "voces.json"
            path.write_text(json.dumps({"_info": "x", "Mayoneso": {"profile": "Mayoneso"}}))
            voices = voice.load_voices(path)
        self.assertEqual(list(voices), ["Mayoneso"])
        self.assertEqual(voices["Mayoneso"].engine, "chatterbox_turbo")

    def test_real_file_has_mayoneso(self):
        self.assertIn("Mayoneso", voice.load_voices())


class SynthesizeTest(unittest.TestCase):
    def test_caches_by_voice_and_text(self):
        client = mock.MagicMock()
        client.generate.side_effect = lambda v, text, out: out.write_bytes(b"wav") or out
        with tempfile.TemporaryDirectory() as tmp:
            a = voice.synthesize("Mayoneso", "I am sleepy.", VOICES, client, Path(tmp))
            b = voice.synthesize("Mayoneso", "I am sleepy.", VOICES, client, Path(tmp))
            c = voice.synthesize("Mayoneso", "I am hungry.", VOICES, client, Path(tmp))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(client.generate.call_count, 2)

    def test_cat_without_voice_fails_clearly(self):
        with self.assertRaisesRegex(voice.VoiceError, "Alioli todavía no tiene voz"):
            voice.synthesize("Alioli", "hi", VOICES, mock.MagicMock())


class VoiceboxClientTest(unittest.TestCase):
    def test_generate_polls_until_completed_and_downloads(self):
        vb = voice.Voicebox()
        responses = {
            ("GET", "/profiles"): [{"id": "p1", "name": "Mayoneso"}],
            ("POST", "/generate"): {"id": "g1", "status": "queued"},
        }
        statuses = iter(["generating", "completed"])

        def fake_json(method, path, body=None):
            if path == "/history/g1":
                return {"status": next(statuses)}
            return responses[(method, path)]

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(vb, "_json", side_effect=fake_json), \
                mock.patch.object(vb, "_call", return_value=b"RIFFdata"), \
                mock.patch.object(voice.time, "sleep"):
            out = vb.generate(VOICES["Mayoneso"], "hi", Path(tmp) / "x.wav")
            self.assertEqual(out.read_bytes(), b"RIFFdata")

    def test_missing_profile(self):
        vb = voice.Voicebox()
        with mock.patch.object(vb, "_json", return_value=[]):
            with self.assertRaisesRegex(voice.VoiceError, "No hay perfil"):
                vb.profile_id("Alioli")

    def test_server_down_message(self):
        vb = voice.Voicebox("http://127.0.0.1:9")
        with self.assertRaisesRegex(voice.VoiceError, "está abierta la app"):
            vb.profile_names()


class DuckingTest(unittest.TestCase):
    def test_envelope_drops_inside_window_only(self):
        env = audio.duck_envelope(3 * SR, [(1.0, 2.0)], -12.0)
        self.assertAlmostEqual(env[int(0.2 * SR)], 1.0, places=3)
        self.assertAlmostEqual(env[int(1.5 * SR)], audio.db(-12.0), places=3)
        self.assertAlmostEqual(env[int(2.8 * SR)], 1.0, places=3)

    def test_no_windows_is_unity(self):
        self.assertTrue(np.all(audio.duck_envelope(100, [], -10.0) == 1.0))


def _plan(**kwargs):
    seg = edl.Segment(src=Path("/v.mp4"), start=0, end=3)
    return edl.Edl(out_dir=Path("/o"), segments=(seg,), **kwargs)


class RenderLinesTest(unittest.TestCase):
    def _spoken(self, subtitle="u wan kno why?"):
        line = edl.Line(cat="Mayoneso", text="You want to know why?", at=0.5,
                        subtitle=subtitle)
        return render.SpokenLine(line, np.full((SR, 2), 0.1), start=0.5)

    def test_subtitle_follows_voice_duration(self):
        [text] = render.subtitle_texts([self._spoken()])
        self.assertEqual(text.text, "u wan kno why?")
        self.assertAlmostEqual(text.dur, 1.0 + render.SUBTITLE_TAIL_S)
        self.assertEqual(text.look, "sticker")
        self.assertEqual(render.subtitle_texts([self._spoken(subtitle=None)]), ())

    def test_voice_in_both_mixes_and_music_ducked(self):
        spoken = [self._spoken()]
        silent = audio.silence(3.0)
        music = np.full((3 * SR + SR // 2, 2), 0.2)
        with mock.patch.object(render, "segment_audio", return_value=silent), \
                mock.patch.object(render.music_mod, "generate",
                                  return_value=(music, {"mood": "cheerful"})):
            main, clean, _ = render.build_mixes(_plan(music=edl.Music(gain_db=0.0)),
                                                [0.0], 3.0, 120.0, spoken)
        self.assertAlmostEqual(clean[int(1.0 * SR), 0], 0.1, places=3)  # voz sin música
        ducked = main[int(1.0 * SR), 0] - 0.1  # música durante la voz
        free = main[int(0.1 * SR), 0]  # música sin voz, antes de la frase y del fundido final
        self.assertLess(ducked, free * 0.5)


class EdlLinesTest(unittest.TestCase):
    def test_lines_load_and_validate_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp4").write_bytes(b"")
            path = Path(tmp) / "edl.json"
            base = {"out_dir": "o", "segments": [{"src": "a.mp4", "start": 0, "end": 2}]}
            path.write_text(json.dumps({**base, "lines": [
                {"cat": "Mayoneso", "text": "I am sleepy.", "subtitle": "im sleepy"}]}))
            loaded = edl.load(path, Path(tmp))
            self.assertEqual(loaded.lines[0].subtitle_look, "sticker")
            self.assertEqual(loaded.duck_db, -10.0)
            path.write_text(json.dumps({**base, "lines": [
                {"cat": "Mayoneso", "text": "x", "segment": 4}]}))
            with self.assertRaisesRegex(ValueError, "segment 4"):
                edl.load(path, Path(tmp))


if __name__ == "__main__":
    unittest.main()
