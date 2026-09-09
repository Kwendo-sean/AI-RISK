import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
        cls.js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    def test_responsive_breakpoints_and_no_fixed_desktop_width(self):
        self.assertIn("@media(max-width:640px)", self.css)
        self.assertIn("@media(max-width:900px)", self.css)
        self.assertIn("min-width:320px", self.css)
        self.assertNotRegex(self.css, r"(?<!max-)width:\s*(?:[4-9]\d\d|\d{4,})px")

    def test_accessibility_contract(self):
        for expected in ("skip-link", "aria-live", "role=\"radiogroup\"", "prefers-reduced-motion", ":focus-visible"):
            self.assertIn(expected, self.html + self.css)
        self.assertNotIn("onclick=", self.html)
        self.assertIn("min-height:44px", self.css)

    def test_privacy_and_progress_controls_exist(self):
        for action in ("edit-profile", "delete-progress", "restart", "resume"):
            self.assertIn(f'data-action="{action}"', self.html)
        self.assertIn("localStorage", self.js)
        self.assertNotIn("sessionStorage.setItem(\"career-survival", self.js)

    def test_no_external_runtime_dependencies(self):
        self.assertNotRegex(self.html, r"https?://")
        self.assertNotIn("ANTHROPIC", self.js.upper())


if __name__ == "__main__":
    unittest.main()
