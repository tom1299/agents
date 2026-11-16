from langchain.tools import tool
from k8s_functions import k8s_core_client, apply_debug_patch

@tool
# TODO: Make this a structured tool and use StructuredTool.from_function
def debug_pod(pod_name: str, namespace: str, debug_container_name: str, debug_image: str, command: list) -> dict:
    """
    Run a command in an ephemeral debug container within a specified pod.
    Similar to `kubectl debug`.

    Args:
        pod_name (str): The name of the pod to debug
        namespace (str): The namespace of the pod.
        debug_container_name (str): The name of the ephemeral container to add.
        debug_image (str): The image for the ephemeral container. E.g "busybox:latest".
        command (list): The command to run in the ephemeral container.

    Returns:
        dict: The updated pod object as a dictionary.
    """
    core_client = k8s_core_client()
    pod = core_client.read_namespaced_pod(name=pod_name, namespace=namespace)
    updated_pod = apply_debug_patch(core_client, pod, debug_container_name, debug_image, command)
    return updated_pod.to_dict()


