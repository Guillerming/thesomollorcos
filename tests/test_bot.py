import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from bot import collector, pipeline, schedule, telegram


def _msg(mid, group=None, kind="photo", caption=None, size=1000):
    m = {"message_id": mid, "chat": {"id": -100}, "from": {"id": 1}}
    if kind == "photo":
        m["photo"] = [{"file_id": f"s{mid}", "file_size": 10},
                      {"file_id": f"b{mid}", "file_size": size}]
    else:
        m["video"] = {"file_id": f"v{mid}", "file_size": size}
    if group:
        m["media_group_id"] = group
    if caption:
        m["caption"] = caption
    return m


class CollectorTest(unittest.TestCase):
    def test_single_photo_is_complete_post_with_largest_size(self):
        post = collector.Collector().add(_msg(1, caption="siesta"))
        self.assertFalse(post.is_album)
        self.assertEqual([m.file_id for m in post.media], ["b1"])
        self.assertEqual(post.texts, ["siesta"])

    def test_album_waits_until_settled(self):
        c = collector.Collector()
        self.assertIsNone(c.add(_msg(1, group="g")))
        self.assertIsNone(c.add(_msg(2, group="g", kind="video")))
        self.assertEqual(c.flush_ready(), [])
        with mock.patch.object(collector.time, "monotonic",
                               return_value=collector.time.monotonic() + 10):
            [post] = c.flush_ready()
        self.assertTrue(post.is_album)
        self.assertEqual([m.kind for m in post.media], ["photo", "video"])

    def test_text_only_message_is_ignored(self):
        msg = {"message_id": 1, "chat": {"id": -100}, "from": {"id": 1}, "text": "hola"}
        self.assertIsNone(collector.Collector().add(msg))

    def test_image_sent_as_file_counts_as_photo(self):
        msg = {"message_id": 1, "chat": {"id": -1}, "from": {"id": 1},
               "document": {"file_id": "d", "mime_type": "image/heic", "file_size": 5}}
        self.assertEqual(collector.extract_media(msg).kind, "photo")


class ScheduleTest(unittest.TestCase):
    def test_reserves_consecutive_free_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            today = date(2026, 10, 29)
            self.assertEqual(schedule.reserve_next_date(path, today), date(2026, 10, 30))
            self.assertEqual(schedule.reserve_next_date(path, today), date(2026, 10, 31))
            self.assertEqual(json.loads(path.read_text())["dates"],
                             ["2026-10-30", "2026-10-31"])


class DescriptionTest(unittest.TestCase):
    def test_includes_link_caption_hashtags_and_idea(self):
        post = {"format": "reel", "files": ["01.mp4"], "caption": "Hoy mando yo",
                "hashtags": ["#gatos", "#siesta"], "suggested_time": "20:00", "notes": "n"}
        text = pipeline.build_description(post, "https://drive/x", Path("/o"), {"text": "idea"})
        for expected in ("[Carpeta en Drive|https://drive/x]", "Hoy mando yo",
                         "#gatos #siesta", "20:00", "idea", "* 01.mp4"):
            self.assertIn(expected, text)

    def test_falls_back_to_local_path_without_link(self):
        text = pipeline.build_description({"files": []}, None, Path("/o/p"), {})
        self.assertIn("/o/p", text)


class LocalTelegramTest(unittest.TestCase):
    def test_host_path_maps_container_volume(self):
        got = telegram.host_path("/var/lib/telegram-bot-api/123:abc/videos/file_0.MP4",
                                 Path("/h/state"))
        self.assertEqual(got, Path("/h/state/123:abc/videos/file_0.MP4"))

    def test_local_download_copies_from_volume_and_frees_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            files_dir, inbox = Path(tmp) / "vol", Path(tmp) / "inbox"
            source = files_dir / "tok" / "videos" / "file_0.MOV"
            source.parent.mkdir(parents=True)
            inbox.mkdir()
            source.write_bytes(b"gato")
            tg = telegram.Telegram("tok", "http://127.0.0.1:8081", files_dir)
            container_path = "/var/lib/telegram-bot-api/tok/videos/file_0.MOV"
            with mock.patch.object(tg, "_call", return_value={"file_path": container_path}):
                saved = tg.download("fid", inbox / "01.mp4")
            self.assertEqual(saved, inbox / "01.mov")
            self.assertEqual(saved.read_bytes(), b"gato")
            self.assertFalse(source.exists())

    def test_get_updates_sends_long_poll_timeout_to_api(self):
        tg = telegram.Telegram("t", "http://x")
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = b'{"ok": true, "result": []}'
        with mock.patch.object(telegram.net, "urlopen", return_value=fake) as urlopen:
            tg.get_updates(offset=5)
        body = urlopen.call_args.kwargs["data"].decode()
        self.assertIn("timeout=2", body)
        self.assertIn("offset=5", body)
        self.assertGreater(urlopen.call_args.kwargs["timeout"], telegram.POLL_TIMEOUT_S)

    def test_limit_depends_on_server(self):
        self.assertEqual(telegram.Telegram("t").max_download_bytes, 20 * 1024 * 1024)
        local = telegram.Telegram("t", "http://x", Path("/v"))
        self.assertEqual(local.max_download_bytes, 2000 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
