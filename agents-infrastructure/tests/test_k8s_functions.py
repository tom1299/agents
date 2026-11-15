import uuid

from kubernetes import client

from tests.k8s_functions import apply_debug_patch, get_ephemeral_container_status

class TestK8sFunctions:

    def test_apply_debug_patch(self, create_pod_with_image, k8s_core_client: client.CoreV1Api):
        ns = "test-debug-patch"
        pod_name = "test-pod"
        image = "nginx:latest"
        create_pod_with_image(ns, pod_name, image)

        pod = k8s_core_client.read_namespaced_pod(name=pod_name, namespace=ns)

        debug_container_name = f"debug-container-{uuid.uuid4().hex[:8]}"
        debug_image = "busybox:latest"

        updated_pod = apply_debug_patch(k8s_core_client, pod, debug_container_name, debug_image)

        assert any(container.name == debug_container_name for container in updated_pod.spec.ephemeral_containers)

        terminated = False
        while not terminated:
            status = get_ephemeral_container_status(k8s_core_client, ns, pod_name, debug_container_name)
            if status and status.state.terminated:
                terminated = True
            else:
                import time
                time.sleep(1)

        logs = k8s_core_client.read_namespaced_pod_log(
            name=pod_name,
            namespace=ns,
            container=debug_container_name,
        )
        assert logs.strip() == "hello"
