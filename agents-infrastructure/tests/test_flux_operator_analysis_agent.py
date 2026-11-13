class TestFluxOperatorAnalysisAgent:

    def test_flux_operator_analysis_agent(self, create_flux_instance) -> None:
        create_flux_instance("flux-instance.yaml")
        assert True, "Flux operator analysis agent test passed successfully."
