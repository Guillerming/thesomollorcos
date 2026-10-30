import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from bot import survey as sv
from bot.collector import Media, PendingPost
from bot.config import Person
from bot.interaction import Interaction

CATS = ("Mayoneso", "Alioli", "Catbleidy")


def _post(kinds=("video",), texts=(), album=False, sender=1):
    return PendingPost(chat_id=-100, sender_id=sender, first_message_id=9, is_album=album,
                       media=[Media(f"f{i}", k, 10) for i, k in enumerate(kinds)],
                       texts=list(texts))


def _keyboard_labels(keyboard):
    return [b["text"] for row in keyboard for b in row]


class FlowTest(unittest.TestCase):
    def test_suggested_format_by_material(self):
        self.assertEqual(sv.suggested_format(_post(("video",))), "reel")
        self.assertEqual(sv.suggested_format(_post(("photo",))), "post")
        self.assertEqual(sv.suggested_format(_post(("photo", "video"), album=True)), "carousel")

    def test_full_flow_format_cats_idea(self):
        s = sv.new_survey(_post())
        s = sv.apply(s, "f", "reel", CATS)
        self.assertEqual(s.step, "cats")
        s = sv.apply(s, "c", "0", CATS)
        s = sv.apply(s, "c", "1", CATS)
        s = sv.apply(s, "c", "0", CATS)  # desmarcar
        self.assertEqual(s.cats, ("Alioli",))
        s = sv.apply(s, "cd", "", CATS)
        self.assertEqual(s.step, "voice")
        s = sv.apply(s, "v", "1", CATS)
        self.assertEqual(s.step, "idea")
        s = sv.set_idea(s, "alioli de parkour")
        self.assertTrue(s.done)
        self.assertEqual(s.answers(),
                         sv.Answers("reel", ("Alioli",), "alioli de parkour", voice=True))

    def test_voice_only_asked_for_video_formats(self):
        post = sv.apply(sv.apply(sv.new_survey(_post()), "f", "post", CATS), "cd", "", CATS)
        self.assertEqual(post.step, "idea")
        story = sv.apply(sv.apply(sv.new_survey(_post()), "f", "story", CATS), "cd", "", CATS)
        self.assertEqual(story.step, "voice")

    def test_back_from_idea_returns_to_voice_and_renders_question(self):
        s = sv.apply(sv.apply(sv.new_survey(_post()), "f", "reel", CATS), "cd", "", CATS)
        _, kb = sv.render(s, CATS, "Guille")
        self.assertIn("🗣 Sí, que hablen", _keyboard_labels(kb))
        s = sv.apply(s, "v", "0", CATS)
        self.assertEqual(sv.apply(s, "back", "", CATS).step, "voice")
        text, _ = sv.render(sv.set_idea(s, "no"), CATS, "Guille")
        self.assertIn("🎙️ Voz: <b>no</b>", text)

    def test_caption_skips_idea_question(self):
        s = sv.apply(sv.new_survey(_post(texts=["siesta"])), "f", "post", CATS)
        s = sv.apply(s, "cn", "", CATS)
        self.assertTrue(s.done)
        self.assertEqual(s.idea, "siesta")

    def test_no_idea_words_and_button(self):
        s = sv.apply(sv.apply(sv.new_survey(_post()), "f", "reel", CATS), "cd", "", CATS)
        s = sv.apply(s, "v", "0", CATS)
        self.assertEqual(sv.set_idea(s, "No").idea, "")
        self.assertTrue(sv.apply(s, "in", "", CATS).done)

    def test_skip_uses_suggestion(self):
        s = sv.apply(sv.new_survey(_post(("photo",))), "skip", "", CATS)
        self.assertTrue(s.done and s.skipped)
        self.assertEqual(s.answers().format, "post")

    def test_back_and_ignored_actions(self):
        s = sv.apply(sv.new_survey(_post()), "f", "story", CATS)
        self.assertEqual(sv.apply(s, "back", "", CATS).step, "format")
        self.assertIs(sv.apply(s, "f", "reel", CATS), s)  # botón de otro paso
        self.assertIs(sv.apply(s, "c", "99", CATS), s)  # índice inexistente

    def test_render_marks_selection_and_suggestion(self):
        s = sv.new_survey(_post())
        text, kb = sv.render(s, CATS, "Guille")
        self.assertIn("🎞 Reel ⭐", _keyboard_labels(kb))
        self.assertIn("Guille", text)
        s = sv.apply(sv.apply(s, "f", "reel", CATS), "c", "2", CATS)
        _, kb = sv.render(s, CATS, "Guille")
        self.assertIn("✅ Catbleidy", _keyboard_labels(kb))
        self.assertTrue(all(len(b["callback_data"]) <= 64 for row in kb for b in row))

    def test_parse_callback(self):
        self.assertEqual(sv.parse_callback("s:ab12cd:c:3"), ("ab12cd", "c", "3"))
        self.assertIsNone(sv.parse_callback("otra:cosa"))


class CatNamesTest(unittest.TestCase):
    def test_reads_first_column_of_both_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gatos.md"
            path.write_text("# Los gatos\n\n| Nombre | Aspecto |\n|---|---|\n"
                            "| Mayoneso | Blanco |\n| Alioli | Blanco |\n\n## Calle\n\n"
                            "| Mu | Vaquita |\n| ? | ? |\n")
            self.assertEqual(sv.load_cat_names(path), ("Mayoneso", "Alioli", "Mu"))

    def test_real_brand_file_has_the_cats(self):
        names = sv.load_cat_names(Path(__file__).parent.parent / "brand" / "gatos.md")
        self.assertIn("Mayoneso", names)
        self.assertIn("Mu", names)


class StoreTest(unittest.TestCase):
    def test_roundtrip_and_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "surveys.json"
            store = sv.SurveyStore(path)
            s = sv.apply(sv.apply(sv.new_survey(_post()), "f", "post", CATS), "cd", "", CATS)
            store.put(replace(s, message_id=77))
            reloaded = sv.SurveyStore(path)
            self.assertEqual(reloaded.by_message(77).sid, s.sid)
            self.assertEqual(reloaded.waiting_idea(1).sid, s.sid)
            self.assertIsNone(reloaded.waiting_idea(2))
            self.assertEqual(reloaded.expired(s.created + sv.SURVEY_TIMEOUT_S + 1)[0].sid, s.sid)


class InteractionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tg = mock.MagicMock()
        self.tg.send_html.return_value = {"message_id": 500}
        cfg = mock.MagicMock()
        cfg.people = {1: Person(1, "Guille", ""), 2: Person(2, "Cata", "")}
        self.queued = []
        self.store = sv.SurveyStore(Path(self.tmp.name) / "s.json")
        self.ui = Interaction(self.tg, cfg, self.store, CATS,
                              lambda post, answers: self.queued.append(answers))

    def tearDown(self):
        self.tmp.cleanup()

    def _press(self, sid, action, value="", user=1):
        self.ui.on_callback({"id": "q", "from": {"id": user},
                             "data": f"s:{sid}:{action}:{value}"})

    def test_end_to_end_with_text_idea(self):
        self.ui.start(_post())
        sid = self.store.by_message(500).sid
        self._press(sid, "f", "reel")
        self._press(sid, "c", "0")
        self._press(sid, "cd")
        self._press(sid, "v", "1")
        used = self.ui.on_text({"text": "mayoneso vs escalera", "from": {"id": 1}})
        self.assertTrue(used)
        self.assertEqual(self.queued, [sv.Answers("reel", ("Mayoneso",), "mayoneso vs escalera",
                                                  voice=True)])
        self.assertIsNone(self.store.get(sid))

    def test_other_person_cannot_answer(self):
        self.ui.start(_post())
        sid = self.store.by_message(500).sid
        self._press(sid, "f", "reel", user=2)
        self.assertEqual(self.store.get(sid).step, "format")
        self.assertTrue(self.tg.answer_callback.call_args.kwargs.get("alert"))

    def test_text_without_open_question_is_ignored(self):
        self.assertFalse(self.ui.on_text({"text": "hola", "from": {"id": 1}}))

    def test_expired_survey_continues_with_defaults(self):
        self.ui.start(_post(("photo",)))
        self.ui.expire_old(now=10 ** 12)
        self.assertEqual(self.queued[0].format, "post")
        self.assertTrue(self.queued[0].skipped)


if __name__ == "__main__":
    unittest.main()
