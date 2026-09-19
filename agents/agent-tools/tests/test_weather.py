from agent_tools.weather import get_weather

class TestWeather:

    def test_get_weather(self) -> None:
        location = "New York"
        expected_output = f"The current weather in {location} is sunny."
        assert get_weather.func(location) == expected_output
