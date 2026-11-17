import time

from kubernetes import client, config
from kubernetes.client import V1EphemeralContainer

# TODO: Complete this list
terminal_waiting_reasons = {
    "ErrImagePull",
    "ImagePullBackOff",
    "InvalidImageName",
    "CreateContainerConfigError",
    "CreateContainerError",
    "RunContainerError",
    "CrashLoopBackOff"
}

# TODO: Currently also used in fixtures of tests => unify
def k8s_core_client() -> client.CoreV1Api:
    config.load_kube_config()
    return client.CoreV1Api()

def get_ingress_ip_v4(networking_client: client.NetworkingV1Api, ingress_name: str, namespace: str) -> str:
    try:
        ingress = networking_client.read_namespaced_ingress(name=ingress_name, namespace=namespace)
        ip = ingress.status.load_balancer.ingress[0].ip
        return ip
    except Exception as exc:
        raise RuntimeError(f"Failed to get ingress IP for {ingress_name} in namespace {namespace}: {exc}")

def wait_for_container_waiting_reason(core_client: client.CoreV1Api, ns: str, pod: str, reasons: set[str], timeout: int = 60) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = core_client.read_namespaced_pod(pod, ns).status.container_statuses or []
        for status in statuses:
            waiting = status.state.waiting
            if waiting and waiting.reason in reasons:
                return waiting.reason
        time.sleep(1)
    raise TimeoutError(f"{ns}/{pod} did not reach any of {reasons} within {timeout}s")

def wait_for_container_running(core_client: client.CoreV1Api, ns: str, pod: str, container: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = core_client.read_namespaced_pod(pod, ns).status.container_statuses or []
        for status in statuses:
            if status.name == container and status.state.running:
                if is_terminal_container_state(status.state):
                    raise RuntimeError(f"{ns}/{pod}/{container} reached terminal state: {status.state}")
                return
        time.sleep(1)
    raise TimeoutError(f"{ns}/{pod}/{container} did not reach running state within {timeout}s")

def wait_for_ephemeral_container_running(core_client: client.CoreV1Api, ns: str, pod: str, container: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = core_client.read_namespaced_pod(pod, ns).status.ephemeral_container_statuses or []
        for status in statuses:
            if status.name == container and (status.state.running or status.state.terminated):
                return
        time.sleep(1)
    raise TimeoutError(f"{ns}/{pod}/{container} did not reach running state within {timeout}s")

def wait_for_ephemeral_container_terminated(core_client: client.CoreV1Api, ns: str, pod: str, container: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = core_client.read_namespaced_pod(pod, ns).status.ephemeral_container_statuses or []
        for status in statuses:
            if status.name == container and status.state.terminated:
                return
        time.sleep(1)
    raise TimeoutError(f"{ns}/{pod}/{container} did not reach terminated state within {timeout}s")

# def is_terminal_container_state(state: client.V1ContainerState) -> bool:
#     return state.terminated is not None or state.waiting is not None and state.waiting.reason in terminal_waiting_reasons

def wait_for_deployment_replicas_ready(apps_client: client.AppsV1Api, ns: str, deployment: str, expected_replicas: int, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dep = apps_client.read_namespaced_deployment(deployment, ns)
        if dep.status.ready_replicas == expected_replicas:
            return
        time.sleep(1)
    raise TimeoutError(f"{ns}/{deployment} did not have {expected_replicas} ready replicas within {timeout}s")

def wait_for_pods_running(core_client: client.CoreV1Api, ns: str, label_selector: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pods = core_client.list_namespaced_pod(ns, label_selector=label_selector).items
        if pods and all(pod.status.phase == "Running" for pod in pods):
            return
        time.sleep(1)
    raise TimeoutError(f"Not all pods in namespace {ns} with label selector {label_selector} are running within {timeout}s")

def wait_for_pod_deletion(core_client: client.CoreV1Api, ns: str, label_selector: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pods = core_client.list_namespaced_pod(ns, label_selector=label_selector).items
        if not pods:
            return
        time.sleep(1)
    raise TimeoutError(f"Pods in namespace {ns} with label selector {label_selector} were not deleted within {timeout}s")

def apply_debug_patch(core_client: client.CoreV1Api, pod: client.V1Pod, name, image, command: list) -> client.V1Pod:
    debug_container = V1EphemeralContainer(
        name=name,
        image=image,
        command=command,
        security_context=client.V1SecurityContext(
            allow_privilege_escalation=False,
            capabilities=client.V1Capabilities(drop=["ALL"]),
            run_as_non_root=True,
            seccomp_profile=client.V1SeccompProfile(type="RuntimeDefault"),
            # TODO: Instead of setting the user name, examine possible error messages when
            # ephemeral container is attached:
            # state:
            # waiting:
            # message: 'container has runAsNonRoot and image will run as root (pod: "test-pod_test-debug-patch(891650af-d46b-45c7-8b03-f78266061ddf)",
            # container: debug - container - 885
            # f1f71)'
            # reason: CreateContainerConfigError
            run_as_user=1000
        ),
    )

    container_json = core_client.api_client.sanitize_for_serialization(debug_container)

    path = "/spec/ephemeralContainers"
    value = [container_json]
    if pod.spec.ephemeral_containers:
        path += "/-"
        value = container_json

    return core_client.patch_namespaced_pod_ephemeralcontainers(
        name=pod.metadata.name,
        namespace=pod.metadata.namespace,
        body=[{"op": "add", "path": path, "value": value}],
        _content_type="application/json-patch+json",
    )

def debug_pod(pod_name: str, namespace: str, debug_container_name,
                      image, command: list) -> str:
    """
    Run a command in an ephemeral debug container within a specified pod.
    Similar to `kubectl debug`.
    :param pod_name: Name of the pod to debug
    :param namespace: Namespace of the pod
    :param debug_container_name: Name of the ephemeral container to add
    :param image: The image for the ephemeral container. E.g "busybox:latest"
    :param command: List of command and arguments to run in the ephemeral container e.g. ["echo", "hello"]
    :return: The output of the command run in the ephemeral container
    """

    pod = k8s_core_client().read_namespaced_pod(pod_name, namespace)
    apply_debug_patch(k8s_core_client(), pod, debug_container_name, image, command)

    wait_for_ephemeral_container_running(k8s_core_client(), namespace, pod_name, debug_container_name, timeout=60)
    wait_for_ephemeral_container_terminated(k8s_core_client(), namespace, pod_name, debug_container_name, timeout=60)

    return k8s_core_client().read_namespaced_pod_log(name=pod_name, namespace=namespace, container=debug_container_name)

def get_ephemeral_container_status(core_client: client.CoreV1Api, ns: str, pod: str, container_name: str) -> client.V1ContainerStatus:
    statuses = core_client.read_namespaced_pod(pod, ns).status.ephemeral_container_statuses or []
    for status in statuses:
        if status.name == container_name:
            return status

    return None
