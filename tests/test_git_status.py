import unittest

from git_steward.git_status import parse_status_z, status_counts, suspect_untracked


class GitStatusTests(unittest.TestCase):
    def test_parse_status_z(self):
        entries = parse_status_z(" M src/app.py\0?? notes.md\0")
        self.assertEqual(entries[0], {"xy": " M", "path": "src/app.py"})
        self.assertEqual(entries[1], {"xy": "??", "path": "notes.md"})

    def test_status_counts(self):
        counts = status_counts(
            [
                {"xy": " M", "path": "a.py"},
                {"xy": "A ", "path": "b.py"},
                {"xy": "??", "path": "c.py"},
            ]
        )
        self.assertEqual(counts["dirty"], 3)
        self.assertEqual(counts["staged"], 1)
        self.assertEqual(counts["unstaged"], 1)
        self.assertEqual(counts["untracked"], 1)

    def test_suspect_untracked_skips_env_examples(self):
        suspects = suspect_untracked([".env", ".env.example", "keys/private.pem", "safe.txt"])
        self.assertEqual(suspects, [".env", "keys/private.pem"])


if __name__ == "__main__":
    unittest.main()
