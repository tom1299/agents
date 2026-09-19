
from agents_common import shared_hello


class TestSharedHello():

    def test_shared_hello(self) -> None:
        assert shared_hello("world") == "Hello, world"
