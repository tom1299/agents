def hello() -> str:
    return "Hello from agents-common!"
from .messages import shared_hello

__all__ = ["shared_hello"]
