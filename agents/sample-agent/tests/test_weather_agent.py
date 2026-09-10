import unittest

from sample_agent.weather_agent import agent

class TestWeatherAgent(unittest.TestCase):

    def test_get_weather(self):
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "What's the weather in San Francisco?"}]}
        )
        expected_output = f"The current weather in San Francisco is sunny."
        self.assertEqual(result["messages"][-1].text, expected_output)