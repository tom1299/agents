import unittest
from io import StringIO
from unittest.mock import patch

from sample_agent.main import main


class SampleAgentMainTests(unittest.TestCase):
    def test_main_prints_shared_greeting(self) -> None:
        buffer = StringIO()
        with patch("sys.stdout", buffer):
            main()

        self.assertEqual(buffer.getvalue().strip(), "Hello, sample-agent")
