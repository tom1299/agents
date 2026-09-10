import unittest
from io import StringIO
from unittest.mock import patch

from agent_tools.main import main


class AgentToolsMainTests(unittest.TestCase):
    def test_main_prints_ready_message(self) -> None:
        buffer = StringIO()
        with patch("sys.stdout", buffer):
            main()

        self.assertEqual(buffer.getvalue().strip(), "agent-tools ready")
