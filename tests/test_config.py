from pathlib import Path
import tempfile
import unittest

from git_steward.config import Config, Root, path_hash, redacted_path


class ConfigTests(unittest.TestCase):
    def test_redacts_home_path(self):
        config = Config(
            path=Path.home() / ".config/git-steward/config.toml",
            roots=[Root(Path.home())],
            state_dir=Path.home() / ".local/state/git-steward",
            redact_paths=True,
        )
        self.assertTrue(redacted_path(config, Path.home() / "Code/example").startswith("~/"))

    def test_path_hash_is_stable_and_not_raw_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            first = path_hash(path)
            second = path_hash(path)
            self.assertEqual(first, second)
            self.assertNotIn(str(path), first)


if __name__ == "__main__":
    unittest.main()
