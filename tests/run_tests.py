# -*- coding: utf-8 -*-
"""
Test Runner.
Discovers and executes all unit and integration tests using unittest.
"""

import sys
import os
import unittest

# Ensure workspace root is in path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def main():
    print("=" * 70)
    print("CAD Standards & Layer QC Analyzer — Automated Test Suite")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    tests_dir = os.path.dirname(os.path.abspath(__file__))
    discovered = loader.discover(start_dir=tests_dir, pattern="test_*.py")
    suite.addTests(discovered)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures:  {len(result.failures)}")
    print(f"Errors:    {len(result.errors)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("ALL TESTS PASSED SUCCESSFULLY!")
        return 0
    else:
        print("SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
