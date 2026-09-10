import tempfile
import unittest
from pathlib import Path

from assignment_assistant.configuration import ConfigurationError, load_config


class ConfigurationTests(unittest.TestCase):
    def test_defaults_are_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = load_config(Path(temporary) / "missing.yaml")
        self.assertEqual(config["discipline"], "auto")
        self.assertTrue(config["human_approval"])
        self.assertEqual(config["external_research"], "ask")

    def test_unknown_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.yaml"
            path.write_text("surprise: yes\n", encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(path)

    def test_human_gates_cannot_be_disabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.yaml"
            path.write_text("human_approval: false\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "must remain true"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
