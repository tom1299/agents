# agents-infrastructure
Kind based Kubernetes cluster for testing agents and agent infrastructure.

## Next steps
* Install ingrss in kind https://kind.sigs.k8s.io/docs/user/ingress/ ✅
* Deploy k8s mcp server and add test using langchain agent to test the mcp server. ✅
* Deploy flux operator and flux operator mcp to test the mcp server. ✅
* Examine helm chart for flux operator mcp for support of ingress / gateway ✅
* Add a test to deploy a flux operator mcp resource and verify that the flux operator mcp is deployed ✅
* Configure kubernetes and flux operator mcp serves to only use "read only" tools (client side) ✅
* Create agent to test troubleshooting a simple problem:
  * Use basic models ✅
  * Capture and assert tool invocations
  * Create separate file for system prompts ✅
  * Examine different models time to solve the problem and tool invocations needed ✅
  * How does memory help with troubleshooting when storing previously troubleshooting steps and their results in a vector database ?
* Speed up fixture deleting pods and namespace
* Move tools creation to fixtures / utils methods
* Examine authentication and authorization for flux operator mcp server and k8s mcp server
  * Possible to select tools based on user identity / role