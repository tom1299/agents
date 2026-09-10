import unittest

from agents_common import shared_hello


class SharedHelloTests(unittest.TestCase):
    def test_shared_hello(self) -> None:
        self.assertEqual(shared_hello("world"), "Hello, world")
