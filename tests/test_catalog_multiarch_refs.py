"""Unit and regression tests for multi-arch source ref parity."""

from pathlib import Path
import unittest

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from check_multiarch_refs import check_parity, extract_arch_refs


SAMPLE_BST_BEFORE = """kind: manual
variables:
  tool_version: v1.0.0

sources:
- kind: remote
  (?):
  - arch == "x86_64":
      url: "https://example.com/tool-%{tool_version}-x86_64.tar.gz"
      ref: 1111111111111111111111111111111111111111111111111111111111111111
  - arch == "aarch64":
      url: "https://example.com/tool-%{tool_version}-aarch64.tar.gz"
      ref: 2222222222222222222222222222222222222222222222222222222222222222
  filename: tool.tar.gz
"""

SAMPLE_BST_X86_ONLY = """kind: manual
variables:
  tool_version: v1.0.1

sources:
- kind: remote
  (?):
  - arch == "x86_64":
      url: "https://example.com/tool-%{tool_version}-x86_64.tar.gz"
      ref: 3333333333333333333333333333333333333333333333333333333333333333
  - arch == "aarch64":
      url: "https://example.com/tool-%{tool_version}-aarch64.tar.gz"
      ref: 2222222222222222222222222222222222222222222222222222222222222222
  filename: tool.tar.gz
"""

SAMPLE_BST_BOTH_BUMPED = """kind: manual
variables:
  tool_version: v1.0.1

sources:
- kind: remote
  (?):
  - arch == "x86_64":
      url: "https://example.com/tool-%{tool_version}-x86_64.tar.gz"
      ref: 3333333333333333333333333333333333333333333333333333333333333333
  - arch == "aarch64":
      url: "https://example.com/tool-%{tool_version}-aarch64.tar.gz"
      ref: 4444444444444444444444444444444444444444444444444444444444444444
  filename: tool.tar.gz
"""

SAMPLE_BST_VERSION_ONLY = """kind: manual
variables:
  tool_version: v1.0.1

sources:
- kind: remote
  (?):
  - arch == "x86_64":
      url: "https://example.com/tool-%{tool_version}-x86_64.tar.gz"
      ref: 1111111111111111111111111111111111111111111111111111111111111111
  - arch == "aarch64":
      url: "https://example.com/tool-%{tool_version}-aarch64.tar.gz"
      ref: 2222222222222222222222222222222222222222222222222222222222222222
  filename: tool.tar.gz
"""


class MultiarchRefParityTests(unittest.TestCase):
    def test_extract_arch_refs(self):
        refs = extract_arch_refs(SAMPLE_BST_BEFORE)
        self.assertEqual(
            refs,
            {
                "x86_64": "1" * 64,
                "aarch64": "2" * 64,
            },
        )

    def test_detects_x86_only_ref_bump(self):
        err = check_parity("elements/tool.bst", SAMPLE_BST_BEFORE, SAMPLE_BST_X86_ONLY)
        self.assertIsNotNone(err)
        self.assertIn("asymmetric multi-arch ref update", err)
        self.assertIn("x86_64 changed=True", err)
        self.assertIn("aarch64 changed=False", err)

    def test_accepts_symmetric_ref_bump(self):
        err = check_parity("elements/tool.bst", SAMPLE_BST_BEFORE, SAMPLE_BST_BOTH_BUMPED)
        self.assertIsNone(err)

    def test_accepts_version_only_bump(self):
        err = check_parity("elements/tool.bst", SAMPLE_BST_BEFORE, SAMPLE_BST_VERSION_ONLY)
        self.assertIsNone(err)

    def test_all_committed_multiarch_elements_have_valid_refs(self):
        root = Path(__file__).parents[1]
        for bst in sorted((root / "elements").rglob("*.bst")):
            content = bst.read_text(encoding="utf-8")
            refs = extract_arch_refs(content)
            if refs:
                self.assertIn("x86_64", refs, f"{bst} defines arch refs but missing x86_64")
                self.assertIn("aarch64", refs, f"{bst} defines arch refs but missing aarch64")
                self.assertEqual(len(refs["x86_64"]), 64, f"{bst} x86_64 ref is not 64-char sha256")
                self.assertEqual(len(refs["aarch64"]), 64, f"{bst} aarch64 ref is not 64-char sha256")


if __name__ == "__main__":
    unittest.main()
