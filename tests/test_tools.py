import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import numpy as np

from tools import edl, music, synth, textcard


def _seg(start, end, speed=1.0):
    return edl.Segment(src=Path("/v.mp4"), start=start, end=end, speed=speed)


class SnapToBeatsTest(unittest.TestCase):
    def test_segments_become_whole_beats(self):
        bpm = 120  # beat = 0.5 s
        snapped = edl.snap_to_beats((_seg(0, 1.3), _seg(5, 5.2)), bpm, {Path("/v.mp4"): 30})
        self.assertAlmostEqual(snapped[0].out_dur, 1.5)
        self.assertAlmostEqual(snapped[1].out_dur, 0.5)  # mínimo 1 beat

    def test_respects_speed_and_source_end(self):
        snapped = edl.snap_to_beats((_seg(9, 10, speed=2.0),), 120, {Path("/v.mp4"): 10})
        self.assertLessEqual(snapped[0].end, 10)
        self.assertAlmostEqual(snapped[0].out_dur, 0.5)

    def test_original_segments_untouched(self):
        original = (_seg(0, 1.3),)
        edl.snap_to_beats(original, 120, {Path("/v.mp4"): 30})
        self.assertEqual(original[0].end, 1.3)


class EdlLoadTest(unittest.TestCase):
    def _write(self, tmp, data):
        path = Path(tmp) / "edl.json"
        path.write_text(json.dumps(data))
        return path

    def test_anchors_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp4").write_bytes(b"")
            path = self._write(tmp, {
                "out_dir": "out", "segments": [{"src": "a.mp4", "start": 0, "end": 2}],
                "texts": [{"text": "im hidimg", "segment": 0}],
                "music": {"mood": "sneaky", "seed": 3},
            })
            loaded = edl.load(path, Path(tmp))
        self.assertEqual(loaded.out_dir, Path(tmp) / "out")
        self.assertEqual(loaded.music.mood, "sneaky")
        self.assertEqual(loaded.clean, "01_sin_musica.mp4")

    def test_rejects_text_on_missing_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.mp4").write_bytes(b"")
            path = self._write(tmp, {
                "out_dir": "out", "segments": [{"src": "a.mp4", "start": 0, "end": 2}],
                "texts": [{"text": "x", "segment": 3}],
            })
            with self.assertRaisesRegex(ValueError, "segment 3"):
                edl.load(path, Path(tmp))

    def test_rejects_end_beyond_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "a.mp4"
            src.write_bytes(b"")
            path = self._write(tmp, {"out_dir": "o",
                                     "segments": [{"src": "a.mp4", "start": 0, "end": 9}]})
            with self.assertRaisesRegex(ValueError, "duración"):
                edl.load(path, Path(tmp), {src: 5.0})

    def test_segment_starts_accumulate_output_time(self):
        self.assertEqual(edl.segment_starts((_seg(0, 2), _seg(5, 9, speed=2.0), _seg(1, 2))),
                         [0.0, 2.0, 4.0])


class TextWindowsTest(unittest.TestCase):
    def test_same_style_texts_do_not_overlap(self):
        from tools import render
        segs = (_seg(0, 2), _seg(2, 4))
        plan = edl.Edl(out_dir=Path("/o"), segments=segs, texts=(
            edl.Text("a", segment=0, at=0.0, dur=3.0),
            edl.Text("b", segment=1, at=0.0, dur=1.0),
            edl.Text("hook", segment=0, at=0.0, dur=3.0, style="hook"),
        ))
        windows = render._text_windows(plan, [0.0, 2.0], 4.0)
        self.assertLess(windows[0][1], windows[1][0])
        self.assertEqual(windows[2], (0.0, 3.0))  # otro estilo: puede convivir


class FitVoiceTest(unittest.TestCase):
    SRC = {Path("/v.mp4"): 30.0}

    def _fit(self, seg, at, dur):
        line = edl.Line(cat="Mayoneso", text="x", segment=0, at=at)
        segs, lines = edl.fit_voice_segments((seg,), (line,), [dur], self.SRC)
        out = segs[0]
        return out, lines[0], out.out_dur - lines[0].at - dur

    def test_one_second_line_gets_1_6_to_2_2_seconds(self):
        for seg in (_seg(0, 1.0), _seg(0, 1.8), _seg(0, 5.0)):
            out, line, after = self._fit(seg, 0.4, 1.0)
            self.assertTrue(1.6 <= out.out_dur <= 2.2, out)
            self.assertTrue(0.3 <= line.at <= 0.6 and 0.3 <= after <= 0.6)

    def test_short_clip_slows_down_before_extending(self):
        out, _, _ = self._fit(_seg(0, 1.6), 0.4, 1.0)
        self.assertLess(out.speed, 1.0)
        self.assertEqual(out.end, 1.6)  # cabe ralentizando: no se alarga

    def test_very_short_clip_extends_end_at_min_speed(self):
        out, _, after = self._fit(_seg(0, 0.5), 0.4, 2.0)
        self.assertEqual(out.speed, edl.MIN_FIT_SPEED)
        self.assertGreater(out.end, 0.5)
        self.assertGreaterEqual(after, 0.3)

    def test_at_is_clamped_into_padding_range(self):
        _, line, _ = self._fit(_seg(0, 3), 0.0, 1.0)
        self.assertEqual(line.at, edl.VOICE_PAD_MIN_S)

    def test_voice_segments_are_not_snapped(self):
        segs = (_seg(0, 1.3), _seg(5, 6.3))
        snapped = edl.snap_to_beats(segs, 120, {Path("/v.mp4"): 30}, keep={1})
        self.assertAlmostEqual(snapped[0].out_dur, 1.5)
        self.assertEqual(snapped[1], segs[1])


class TextSfxTest(unittest.TestCase):
    def _names(self, *texts):
        plan = edl.Edl(out_dir=Path("/o"), segments=(_seg(0, 2),) * 6, texts=texts)
        return edl.resolve_text_sfx(plan, synth.CARTEL_SFX)

    def test_styles_overrides_and_disabled(self):
        names = self._names(edl.Text("a", style="punch"), edl.Text("b", style="hook"),
                            edl.Text("c", sfx=None, segment=1), edl.Text("d", sfx="jp_zun",
                                                                          segment=2))
        self.assertEqual(names, ["jp_don", None, None, "jp_zun"])

    def test_label_sounds_rotate_and_never_repeat_back_to_back(self):
        names = self._names(*(edl.Text(str(i), segment=i) for i in range(6)))
        self.assertTrue(all(n in synth.CARTEL_SFX for n in names))
        self.assertTrue(all(a != b for a, b in zip(names, names[1:])))
        self.assertGreaterEqual(len(set(names)), 3)

    def test_rotation_skips_sound_chosen_just_before(self):
        names = self._names(edl.Text("a", sfx="jp_pikon", segment=0), edl.Text("b", segment=1))
        self.assertNotEqual(names[1], "jp_pikon")

    def test_reading_time_grows_with_words(self):
        self.assertAlmostEqual(edl.reading_time("u comin or wat"), 1.6)
        self.assertGreater(edl.reading_time("i even carry it mysel for u"), 2.0)

    def test_blip_lands_when_text_appears(self):
        from tools import render
        from tools.audio import silence
        plan = edl.Edl(out_dir=Path("/o"), segments=(_seg(0, 3),),
                       texts=(edl.Text("hehe", segment=0, at=1.0, dur=1.5),))
        with unittest.mock.patch.object(render, "segment_audio", return_value=silence(3.0)):
            _, clean, _ = render.build_mixes(plan, [0.0], 3.0, None)
        before = np.abs(clean[: int(0.9 * synth.SR)]).max()
        after = np.abs(clean[int(1.0 * synth.SR): int(1.3 * synth.SR)]).max()
        self.assertEqual(before, 0.0)
        self.assertGreater(after, 0.05)


class MusicTest(unittest.TestCase):
    def test_length_beats_and_determinism(self):
        a, info = music.generate(6.0, "cheerful", bpm=120, seed=5)
        b, _ = music.generate(6.0, "cheerful", bpm=120, seed=5)
        self.assertEqual(a.shape, (6 * synth.SR, 2))
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(info["beats"][:3], [0.0, 0.5, 1.0])
        self.assertLessEqual(float(np.max(np.abs(a))), 0.9)
        self.assertGreater(float(np.std(a)), 0.01)

    def test_every_mood_renders(self):
        for mood in music.MOODS:
            audio, info = music.generate(3.0, mood, seed=1)
            lo, hi = music.MOODS[mood].bpm_range
            self.assertTrue(lo <= info["bpm"] <= hi, mood)
            self.assertFalse(np.isnan(audio).any(), mood)

    def test_unknown_mood_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "mood desconocido"):
            music.generate(2.0, "angry")

    def test_all_sfx_are_audible(self):
        rng = np.random.default_rng(0)
        for name, fn in synth.SFX.items():
            self.assertGreater(float(np.max(np.abs(fn(rng)))), 0.05, name)


class TextcardTest(unittest.TestCase):
    def test_hook_stays_in_top_safe_zone(self):
        img = textcard.render("i smel flower nice smel wow", "hook")
        self.assertEqual(img.size, (1080, 1920))
        top, bottom = img.getbbox()[1], img.getbbox()[3]
        self.assertGreater(top, 1920 * 0.08)
        self.assertLess(bottom, 1920 * 0.40)

    def test_long_text_shrinks_to_three_lines_max(self):
        img = textcard.render(" ".join(["demtists"] * 14), "label")
        box = img.getbbox()
        self.assertLess(box[2] - box[0], 1080 * 0.9)

    def test_wrap_balances_lines_without_orphans(self):
        font, lines = textcard._fit("wak wif teh gang", textcard.STYLES["cover"], 1080)
        if len(lines) == 2:
            self.assertGreater(len(lines[1].split()), 1, lines)

    def test_custom_y_moves_block(self):
        low = textcard.render("im hidimg", "cover", y=0.70).getbbox()
        high = textcard.render("im hidimg", "cover", y=0.24).getbbox()
        self.assertGreater(low[1], high[3])

    def test_unknown_style_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "style desconocido"):
            textcard.render("x", "giant")


if __name__ == "__main__":
    unittest.main()
