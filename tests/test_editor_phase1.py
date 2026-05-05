import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import editor


def _write_file(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class EditorPhase1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.footage_root = self.root / "footage"
        self.output_path = self.root / "final.mp4"
        self.brief_path = self.root / "brief.json"

        source_clip = self.root / "clip.mp4"
        _write_file(source_clip, "fake-video")

        niche_dir = self.footage_root / "dark_motivation"
        index_path = niche_dir / "index.json"
        index_payload = {
            "keywords": {
                "battle": {
                    "clips": [{"file": str(source_clip)}]
                }
            }
        }
        _write_file(index_path, json.dumps(index_payload))

        brief = {
            "vibe": {"niche": "dark motivation"},
            "music_mood": "epic",
            "shots": [
                {
                    "shot_number": 1,
                    "footage_keyword": "battle",
                    "clip_duration_secs": 2.0,
                    "text_overlay": "",
                    "transition_out": "cut",
                    "color_grade": "none",
                }
            ],
        }
        _write_file(self.brief_path, json.dumps(brief))

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _fake_copy_pipeline(input_path, output_path, *args, **kwargs):
        Path(output_path).write_text("generated")

    @patch("editor.add_watermark")
    @patch("editor.mix_music")
    @patch("editor.find_music", return_value=None)
    @patch("editor.concat_clips")
    @patch("editor.add_text_overlay")
    @patch("editor.apply_color_grade")
    @patch("editor.extract_segment")
    @patch("editor.select_and_extract", return_value=True)
    def test_editor_uses_clip_selector_before_fallback(
        self,
        mock_select,
        mock_extract_fallback,
        mock_grade,
        mock_text,
        mock_concat,
        _mock_music,
        mock_mix,
        mock_watermark,
    ):
        mock_grade.side_effect = self._fake_copy_pipeline
        mock_text.side_effect = self._fake_copy_pipeline
        mock_concat.side_effect = self._fake_copy_pipeline
        mock_mix.side_effect = self._fake_copy_pipeline
        mock_watermark.side_effect = self._fake_copy_pipeline

        with patch("editor.FOOTAGE_ROOT", self.footage_root):
            ok = editor.assemble(
                str(self.brief_path),
                str(self.output_path),
                seed=123,
                production=False,
            )

        self.assertTrue(ok)
        self.assertTrue(mock_select.called)
        mock_extract_fallback.assert_not_called()

    @patch("editor.add_watermark")
    @patch("editor.mix_music")
    @patch("editor.find_music", return_value=None)
    @patch("editor.concat_clips")
    @patch("editor.add_text_overlay")
    @patch("editor.apply_color_grade")
    @patch("editor.extract_segment", return_value=True)
    @patch("editor.select_and_extract", return_value=False)
    def test_editor_fallback_on_selector_failure(
        self,
        _mock_select,
        mock_extract_fallback,
        mock_grade,
        mock_text,
        mock_concat,
        _mock_music,
        mock_mix,
        mock_watermark,
    ):
        mock_grade.side_effect = self._fake_copy_pipeline
        mock_text.side_effect = self._fake_copy_pipeline
        mock_concat.side_effect = self._fake_copy_pipeline
        mock_mix.side_effect = self._fake_copy_pipeline
        mock_watermark.side_effect = self._fake_copy_pipeline

        with patch("editor.FOOTAGE_ROOT", self.footage_root):
            ok = editor.assemble(str(self.brief_path), str(self.output_path), seed=7)

        self.assertTrue(ok)
        self.assertTrue(mock_extract_fallback.called)

    def test_editor_production_requires_scenedetect(self):
        with patch("editor.SCENEDETECT_AVAILABLE", False):
            with self.assertRaises(RuntimeError):
                editor.assemble(
                    str(self.brief_path),
                    str(self.output_path),
                    production=True,
                )


if __name__ == "__main__":
    unittest.main()
