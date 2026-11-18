import uuid

from kubernetes import client

from agents_infrastructure.k8s_functions import debug_pod, get_ephemeral_container_status

class TestK8sFunctions:

    def test_apply_debug_patch(self, create_pod_with_image, k8s_core_client: client.CoreV1Api):
        ns = "test-debug-patch"
        pod_name = "test-pod"
        image = "nginx:latest"
        create_pod_with_image(ns, pod_name, image)

        debug_image = "busybox:latest"

        debug_container_names = [f"debug-container-{uuid.uuid4().hex[:8]}" for _ in range(2)]
        for debug_container_name in debug_container_names:

            k8s_core_client.read_namespaced_pod(name=pod_name, namespace=ns)
            command = ["echo", f"hello from {debug_container_name}"]
            output = debug_pod(pod_name, ns, debug_container_name, debug_image, command)
            assert output.strip() == f"hello from {debug_container_name}"

        # TODO: Check order of ephemeral containers in the pod
