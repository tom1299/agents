import unittest

from agent_tools.weather import get_weather

class WeatherTests(unittest.TestCase):

    def test_get_weather(self) -> None:
        location = "New York"
        expected_output = f"The current weather in {location} is sunny."
        self.assertEqual(get_weather.func(location), expected_output)
