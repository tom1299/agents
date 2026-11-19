import inspect

from pytest import mark

from tests.test_flux_operator_analysis_agent import TestFluxOperatorAnalysisAgent as FluxTests
from tests.test_k8s_analysis_agent import TestAnalystAgent as KubernetesTests


@mark.parametrize("test_class", [FluxTests, KubernetesTests])
def test_analysis_agent_tests_share_session_loop(test_class) -> None:
    methods = [
        method
        for name, method in inspect.getmembers(test_class, inspect.iscoroutinefunction)
        if name.startswith("test_")
    ]
    assert methods
    for method in methods:
        asyncio_mark = next(mark for mark in method.pytestmark if mark.name == "asyncio")
        assert asyncio_mark.kwargs.get("loop_scope") == "session"
